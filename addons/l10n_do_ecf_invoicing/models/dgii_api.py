import base64
import logging
import os
import subprocess
import tempfile

import requests
from lxml import etree

from cryptography.hazmat.primitives.serialization import pkcs12

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

XMLDSIG_NS = "http://www.w3.org/2000/09/xmldsig#"

# Path to the generic signing script (mounted into the Docker container)
# On the host: /tmp/dgii-sign/sign_generic.mjs
# Inside container: /dgii-sign/sign_generic.mjs
_SIGN_SCRIPT = os.environ.get("DGII_SIGN_SCRIPT", "/dgii-sign/sign_generic.mjs")
_NODE_BIN = os.environ.get("NODE_BIN", "/usr/local/bin/node")

REQUEST_TIMEOUT = 30


class DgiiApi(models.AbstractModel):
    """Handles all DGII API communication: authentication, sending e-CF, polling."""

    _name = "l10n_do.dgii.api"
    _description = "DGII e-CF API Client"

    # -------------------------------------------------------------------------
    # Certificate helpers
    # -------------------------------------------------------------------------
    @api.model
    def _load_p12(self, p12_bytes, password):
        """Load a P12 certificate and return (private_key, certificate, chain)."""
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            p12_bytes, password
        )
        return private_key, certificate, chain

    # -------------------------------------------------------------------------
    # XML signing via dgii-ecf npm package (Node.js subprocess)
    # -------------------------------------------------------------------------
    @api.model
    def _sign_xml_with_node(self, xml_bytes, p12_bytes, password, root_el_name):
        """Sign XML using the dgii-ecf npm package via Node.js subprocess.

        This is the ONLY signing method that produces output accepted by DGII.
        The dgii-ecf package handles the namespace attribute alphabetical sorting
        required by DGII's digest verification (a 3-day discovery by the package
        author — see Digest.js in dgii-ecf source).

        Args:
            xml_bytes: bytes — the unsigned XML
            p12_bytes: bytes — the P12/PFX certificate
            password:  str   — certificate password
            root_el_name: str — root element name (e.g. 'ECF', 'SemillaModel', 'Postulacion')

        Returns:
            bytes — the signed XML
        """
        if not os.path.exists(_NODE_BIN):
            raise UserError(
                _(
                    "Node.js not found at %s.\n"
                    "The DGII signing requires Node.js mounted in the Docker container.\n"
                    "Check docker-compose.yml volumes.",
                    _NODE_BIN,
                )
            )
        if not os.path.exists(_SIGN_SCRIPT):
            raise UserError(
                _(
                    "DGII signing script not found at %s.\n"
                    "Mount /tmp/dgii-sign into the container as /dgii-sign.",
                    _SIGN_SCRIPT,
                )
            )

        with tempfile.TemporaryDirectory(prefix="dgii_sign_") as tmpdir:
            input_path  = os.path.join(tmpdir, "input.xml")
            output_path = os.path.join(tmpdir, "signed.xml")
            p12_path    = os.path.join(tmpdir, "cert.p12")

            with open(input_path, "wb") as f:
                f.write(xml_bytes)
            with open(p12_path, "wb") as f:
                f.write(p12_bytes)

            cmd = [
                _NODE_BIN,
                _SIGN_SCRIPT,
                input_path,
                output_path,
                p12_path,
                password if isinstance(password, str) else password.decode("utf-8"),
                root_el_name,
            ]

            _logger.info("DGII Sign: running %s for <%s>", _NODE_BIN, root_el_name)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired as e:
                raise UserError(_("DGII signing timed out: %s", str(e))) from e
            except FileNotFoundError as e:
                raise UserError(
                    _("Node.js binary not found: %s", str(e))
                ) from e

            if result.returncode != 0:
                raise UserError(
                    _(
                        "DGII signing failed (exit %s):\n%s\n%s",
                        result.returncode,
                        result.stdout,
                        result.stderr,
                    )
                )

            _logger.info("DGII Sign: %s", result.stdout.strip())
            with open(output_path, "rb") as f:
                return f.read()

    # -------------------------------------------------------------------------
    # Authentication: semilla (seed) flow
    # -------------------------------------------------------------------------
    def _authenticate(self, company):
        """Perform the DGII seed authentication flow.

        1. GET /Autenticacion/api/Autenticacion/Semilla → seed XML
        2. Sign the seed XML with the company's P12 certificate (via Node.js)
        3. POST signed seed → /autenticacion/api/Autenticacion/ValidarSemilla → JWT

        Returns the JWT bearer token string.
        """
        endpoints = company._get_l10n_do_ecf_endpoints()
        p12_bytes, password = company._get_l10n_do_ecf_certificate_data()
        if not p12_bytes:
            raise UserError(
                _("No e-CF certificate configured for company %s.", company.name)
            )

        # Step 1: Get seed
        seed_url = endpoints["auth_seed"]
        _logger.info("DGII Auth: requesting seed from %s", seed_url)
        try:
            resp = requests.get(seed_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise UserError(
                _("Failed to obtain DGII seed: %s", str(e))
            ) from e

        seed_xml_bytes = resp.content

        # Step 2: Sign the seed XML (root element is <SemillaModel>)
        signed_seed_bytes = self._sign_xml_with_node(
            xml_bytes=seed_xml_bytes,
            p12_bytes=p12_bytes,
            password=password.decode("utf-8") if isinstance(password, bytes) else (password or ""),
            root_el_name="SemillaModel",
        )

        # Step 3: POST signed seed
        validate_url = endpoints["auth_validate"]
        _logger.info("DGII Auth: posting signed seed to %s", validate_url)
        try:
            resp = requests.post(
                validate_url,
                files={"xml": ("seed.xml", signed_seed_bytes, "text/xml")},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise UserError(
                _("DGII certificate validation failed: %s", str(e))
            ) from e

        try:
            data = resp.json()
            token = data.get("token", "").strip().strip('"') if isinstance(data, dict) else resp.text.strip().strip('"')
        except Exception:
            token = resp.text.strip().strip('"')
        if not token:
            raise UserError(_("DGII returned an empty authentication token."))

        _logger.info("DGII Auth: obtained token (length=%d, prefix=%s)", len(token), token[:20])
        return token

    # -------------------------------------------------------------------------
    # Send e-CF
    # -------------------------------------------------------------------------
    def _send_ecf(self, company, xml_bytes, filename, ecf_type_code=None, already_signed=False):
        """Generate, sign, and send an e-CF XML to DGII.

        Args:
            company: res.company record
            xml_bytes: bytes of the XML document (unsigned or signed)
            filename: filename for the multipart upload
            ecf_type_code: str like '32', '44', etc. (determines RFCE vs regular endpoint)
            already_signed: if True, xml_bytes is already signed; skip re-signing

        Returns:
            dict with keys: trackId, mensaje, estado, etc.
        """
        p12_bytes, password = company._get_l10n_do_ecf_certificate_data()
        if not p12_bytes:
            raise UserError(
                _("No e-CF certificate configured for company %s.", company.name)
            )

        if already_signed:
            signed_xml_bytes = xml_bytes
        else:
            # Sign the e-CF XML (root element is always <ECF>)
            signed_xml_bytes = self._sign_xml_with_node(
                xml_bytes=xml_bytes,
                p12_bytes=p12_bytes,
                password=password.decode("utf-8") if isinstance(password, bytes) else (password or ""),
                root_el_name="ECF",
            )

        token = self._authenticate(company)
        endpoints = company._get_l10n_do_ecf_endpoints()

        # E32 < 250K uses the RFCE endpoint (fc.dgii.gov.do)
        if ecf_type_code == "32":
            send_url = endpoints["send_rfce"]
        else:
            send_url = endpoints["send_ecf"]

        headers = {"Authorization": f"Bearer {token}"}
        _logger.info(
            "DGII Send: posting e-CF (%s) to %s (type_code=%s, size=%d bytes)",
            filename, send_url, ecf_type_code, len(signed_xml_bytes)
        )

        try:
            resp = requests.post(
                send_url,
                headers=headers,
                files={"xml": (filename, signed_xml_bytes, "text/xml")},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise UserError(
                _("Failed to send e-CF to DGII: %s", str(e))
            ) from e

        if resp.status_code == 401:
            _logger.error(
                "DGII Send: 401 Unauthorized. URL=%s, Headers sent=%s, Response headers=%s, Response body=%s",
                send_url, dict(headers), dict(resp.headers), resp.text
            )
            raise UserError(
                _(
                    "DGII authentication expired or invalid. "
                    "URL: %s\n"
                    "Response: %s\n"
                    "Check your certificate and try again.",
                    send_url, resp.text[:500]
                )
            )

        _logger.info(
            "DGII Send: HTTP %s, body=%s",
            resp.status_code, resp.text[:2000]
        )
        try:
            result = resp.json()
        except ValueError:
            result = {"status": resp.status_code, "message": resp.text}

        _logger.info("DGII Send: parsed response=%s", result)
        return result

    # -------------------------------------------------------------------------
    # Poll status
    # -------------------------------------------------------------------------
    def _poll_status(self, company, track_id):
        """Poll DGII for the status of a previously sent e-CF.

        Args:
            company: res.company record
            track_id: the trackId returned by _send_ecf

        Returns:
            dict with status information from DGII
        """
        token = self._authenticate(company)
        endpoints = company._get_l10n_do_ecf_endpoints()
        status_url = endpoints["poll_status"]

        headers = {"Authorization": f"Bearer {token}"}
        params = {"trackId": track_id}
        _logger.info("DGII Poll: checking status at %s (trackId=%s)", status_url, track_id)

        try:
            resp = requests.get(
                status_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise UserError(
                _("Failed to check e-CF status with DGII: %s", str(e))
            ) from e

        try:
            result = resp.json()
        except ValueError:
            result = {"status": resp.status_code, "message": resp.text}

        _logger.info("DGII Poll: response=%s", result)
        return result

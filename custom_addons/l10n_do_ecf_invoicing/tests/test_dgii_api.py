"""
Tests for the DGII API client.

Tests the XML signing, authentication flow, and API communication.
Uses mocks for external HTTP calls and certificate operations.
"""
import base64
import hashlib
from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_do_ecf")
class TestDgiiApi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({
            "country_id": cls.env.ref("base.do").id,
            "vat": "130862346",
            "name": "Test Company SRL",
            "l10n_do_ecf_service_env": "test",
        })
        cls.dgii_api = cls.env["l10n_do.dgii.api"]

    def test_base_url_test_env(self):
        """Test environment returns test URL."""
        self.company.l10n_do_ecf_service_env = "test"
        url = self.company._get_l10n_do_ecf_base_url()
        self.assertEqual(url, "https://ecf.dgii.gov.do/testecf/")

    def test_base_url_production_env(self):
        """Production environment returns production URL."""
        self.company.l10n_do_ecf_service_env = "production"
        url = self.company._get_l10n_do_ecf_base_url()
        self.assertEqual(url, "https://ecf.dgii.gov.do/ecf/")

    def test_compute_digest(self):
        """Test SHA-256 digest computation of XML."""
        xml = etree.Element("ECF")
        etree.SubElement(xml, "Test").text = "Hello"
        digest = self.dgii_api._compute_digest(xml)

        # Verify it's valid base64
        decoded = base64.b64decode(digest)
        self.assertEqual(len(decoded), 32)  # SHA-256 = 32 bytes

    def test_build_signed_info(self):
        """Test SignedInfo element structure."""
        digest = base64.b64encode(b"test_digest_value").decode()
        signed_info = self.dgii_api._build_signed_info(digest)

        ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        self.assertEqual(signed_info.tag, "{http://www.w3.org/2000/09/xmldsig#}SignedInfo")

        c14n = signed_info.find("ds:CanonicalizationMethod", ns)
        self.assertIsNotNone(c14n)
        self.assertEqual(
            c14n.get("Algorithm"),
            "http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )

        sig_method = signed_info.find("ds:SignatureMethod", ns)
        self.assertIsNotNone(sig_method)
        self.assertEqual(
            sig_method.get("Algorithm"),
            "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
        )

        ref = signed_info.find("ds:Reference", ns)
        self.assertIsNotNone(ref)
        self.assertEqual(ref.get("URI"), "")

        digest_method = ref.find("ds:DigestMethod", ns)
        self.assertEqual(
            digest_method.get("Algorithm"),
            "http://www.w3.org/2001/04/xmlenc#sha256",
        )

    @patch("odoo.addons.l10n_do_ecf_invoicing.models.dgii_api.requests")
    def test_authenticate_calls_correct_urls(self, mock_requests):
        """Test authentication flow calls correct endpoints."""
        # Mock seed response
        seed_xml = b'<?xml version="1.0"?><SemillaModel><valor>test_seed</valor></SemillaModel>'
        mock_seed_resp = MagicMock()
        mock_seed_resp.content = seed_xml
        mock_seed_resp.raise_for_status = MagicMock()

        # Mock token response
        mock_token_resp = MagicMock()
        mock_token_resp.text = '"test_jwt_token_123"'
        mock_token_resp.raise_for_status = MagicMock()

        mock_requests.get.return_value = mock_seed_resp
        mock_requests.post.return_value = mock_token_resp

        # Mock certificate
        mock_key = MagicMock()
        mock_key.sign.return_value = b"fake_signature"
        mock_cert = MagicMock()
        mock_cert.public_bytes.return_value = b"fake_cert_der"

        with patch.object(
            self.dgii_api, "_load_p12", return_value=(mock_key, mock_cert, None)
        ):
            self.company.write({
                "l10n_do_ecf_certificate": base64.b64encode(b"fake_p12"),
                "l10n_do_ecf_certificate_password": "test",
            })
            token = self.dgii_api._authenticate(self.company)

        self.assertEqual(token, "test_jwt_token_123")
        mock_requests.get.assert_called_once()
        mock_requests.post.assert_called_once()

        # Verify URLs
        get_url = mock_requests.get.call_args[0][0]
        self.assertIn("testecf/autenticacion/api/semilla", get_url)
        post_url = mock_requests.post.call_args[0][0]
        self.assertIn("testecf/autenticacion/api/validacioncertificado", post_url)

    @patch("odoo.addons.l10n_do_ecf_invoicing.models.dgii_api.requests")
    def test_send_ecf_returns_result(self, mock_requests):
        """Test sending e-CF returns DGII response."""
        # Mock auth
        seed_xml = b'<?xml version="1.0"?><SemillaModel><valor>seed</valor></SemillaModel>'
        mock_seed_resp = MagicMock()
        mock_seed_resp.content = seed_xml
        mock_seed_resp.raise_for_status = MagicMock()

        mock_token_resp = MagicMock()
        mock_token_resp.text = '"jwt_token"'
        mock_token_resp.raise_for_status = MagicMock()
        mock_token_resp.status_code = 200

        # Mock send response
        mock_send_resp = MagicMock()
        mock_send_resp.status_code = 200
        mock_send_resp.json.return_value = {
            "trackId": "track-123",
            "mensaje": "Recibido",
            "estado": "EnProceso",
        }

        mock_requests.get.return_value = mock_seed_resp
        mock_requests.post.side_effect = [mock_token_resp, mock_send_resp]

        mock_key = MagicMock()
        mock_key.sign.return_value = b"fake_signature"
        mock_cert = MagicMock()
        mock_cert.public_bytes.return_value = b"fake_cert_der"

        with patch.object(
            self.dgii_api, "_load_p12", return_value=(mock_key, mock_cert, None)
        ):
            self.company.write({
                "l10n_do_ecf_certificate": base64.b64encode(b"fake_p12"),
                "l10n_do_ecf_certificate_password": "test",
            })
            result = self.dgii_api._send_ecf(
                self.company, b"<ECF/>", "test.xml"
            )

        self.assertEqual(result["trackId"], "track-123")
        self.assertEqual(result["estado"], "EnProceso")

    @patch("odoo.addons.l10n_do_ecf_invoicing.models.dgii_api.requests")
    def test_poll_status(self, mock_requests):
        """Test polling for e-CF status."""
        seed_xml = b'<?xml version="1.0"?><SemillaModel><valor>seed</valor></SemillaModel>'
        mock_seed_resp = MagicMock()
        mock_seed_resp.content = seed_xml
        mock_seed_resp.raise_for_status = MagicMock()

        mock_token_resp = MagicMock()
        mock_token_resp.text = '"jwt_token"'
        mock_token_resp.raise_for_status = MagicMock()

        mock_status_resp = MagicMock()
        mock_status_resp.json.return_value = {
            "estado": "Aceptado",
            "mensaje": "e-CF aceptado",
            "codigoSeguridad": "ABC123",
            "fechaFirma": "15-01-2025 14:30:00",
        }
        mock_status_resp.raise_for_status = MagicMock()

        # First GET = seed, second GET = status
        mock_requests.get.side_effect = [mock_seed_resp, mock_status_resp]
        mock_requests.post.return_value = mock_token_resp

        mock_key = MagicMock()
        mock_key.sign.return_value = b"fake_signature"
        mock_cert = MagicMock()
        mock_cert.public_bytes.return_value = b"fake_cert_der"

        with patch.object(
            self.dgii_api, "_load_p12", return_value=(mock_key, mock_cert, None)
        ):
            self.company.write({
                "l10n_do_ecf_certificate": base64.b64encode(b"fake_p12"),
                "l10n_do_ecf_certificate_password": "test",
            })
            result = self.dgii_api._poll_status(self.company, "track-123")

        self.assertEqual(result["estado"], "Aceptado")
        self.assertEqual(result["codigoSeguridad"], "ABC123")

    def test_digest_excludes_signature(self):
        """Test that digest computation excludes existing Signature element."""
        ns = "http://www.w3.org/2000/09/xmldsig#"
        xml = etree.Element("ECF")
        etree.SubElement(xml, "Data").text = "test"
        sig = etree.SubElement(xml, f"{{{ns}}}Signature")
        etree.SubElement(sig, f"{{{ns}}}SignatureValue").text = "old_sig"

        digest = self.dgii_api._compute_digest(xml)

        # Compute expected: XML without Signature
        expected_xml = etree.Element("ECF")
        etree.SubElement(expected_xml, "Data").text = "test"
        expected_c14n = etree.tostring(expected_xml, method="c14n")
        expected_digest = base64.b64encode(
            hashlib.sha256(expected_c14n).digest()
        ).decode()

        self.assertEqual(digest, expected_digest)

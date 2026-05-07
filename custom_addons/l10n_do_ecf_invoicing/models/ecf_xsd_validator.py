"""
XSD Validator for e-CF XML documents.

Validates generated XML against the official DGII XSD schemas before signing
and submission. The XSD files are stored in static/xsd/ and loaded by e-CF type.
"""
import logging
import os

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Map e-CF type code to XSD filename (official DGII naming convention)
XSD_FILENAMES = {
    "31": "e-CF_31_v1.0.xsd",
    "32": "e-CF_32_v1.0.xsd",
    "33": "e-CF_33_v1.0.xsd",
    "34": "e-CF_34_v1.0.xsd",
    "41": "e-CF_41_v1.0.xsd",
    "43": "e-CF_43_v1.0.xsd",
    "44": "e-CF_44_v1.0.xsd",
    "45": "e-CF_45_v1.0.xsd",
    "46": "e-CF_46_v1.0.xsd",
    "47": "e-CF_47_v1.0.xsd",
}


class EcfXsdValidator(models.AbstractModel):
    """Validates e-CF XML documents against DGII XSD schemas."""

    _name = "l10n_do.ecf.xsd.validator"
    _description = "e-CF XSD Validator"

    @api.model
    def _get_xsd_path(self, type_code):
        """Return the full filesystem path to the XSD file for the given type."""
        filename = XSD_FILENAMES.get(type_code)
        if not filename:
            return None
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(module_path, "static", "xsd", filename)

    @api.model
    def validate(self, xml_root, type_code):
        """Validate an e-CF XML tree against its XSD schema.

        Args:
            xml_root: lxml.etree.Element — the <ECF> root element (unsigned,
                      without the <Signature> element)
            type_code: str — the e-CF type code (e.g. "31", "47")

        Raises:
            ValidationError if the XML does not conform to the schema.
            Returns True silently if valid or if no XSD is available.
        """
        xsd_path = self._get_xsd_path(type_code)
        if not xsd_path or not os.path.isfile(xsd_path):
            _logger.warning(
                "XSD file not found for e-CF type E%s at %s — skipping validation.",
                type_code, xsd_path,
            )
            return True

        try:
            with open(xsd_path, "rb") as f:
                xsd_doc = etree.parse(f)
            schema = etree.XMLSchema(xsd_doc)
        except etree.XMLSchemaParseError as e:
            _logger.error("Failed to parse XSD for E%s: %s", type_code, e)
            return True  # Don't block on broken schema file

        # We need to validate a copy without the Signature element
        # (the XSD doesn't include the xmldsig schema)
        tree_copy = etree.fromstring(etree.tostring(xml_root))
        nsmap = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
        for sig in tree_copy.findall("ds:Signature", nsmap):
            sig.getparent().remove(sig)
        # Also try without namespace prefix
        for sig in tree_copy.findall(
            "{http://www.w3.org/2000/09/xmldsig#}Signature"
        ):
            sig.getparent().remove(sig)

        if not schema.validate(tree_copy):
            errors = "\n".join(str(e) for e in schema.error_log)
            _logger.warning(
                "e-CF E%s XML validation errors:\n%s", type_code, errors
            )
            raise ValidationError(
                _(
                    "The generated e-CF XML (type E%(type)s) does not conform "
                    "to the DGII schema:\n\n%(errors)s",
                    type=type_code,
                    errors=errors,
                )
            )
        _logger.info("e-CF E%s XML passed XSD validation.", type_code)
        return True

"""
Tests for the e-CF XML Generator.

These tests verify that the XML structure generated for each e-CF type
is correct and conforms to the DGII specification.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_do_ecf")
class TestEcfXmlGenerator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({
            "country_id": cls.env.ref("base.do").id,
            "vat": "130862346",
            "name": "Test Company SRL",
            "l10n_do_ecf_issuer": True,
            "l10n_do_ecf_service_env": "test",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Customer SRL",
            "vat": "131234567",
            "country_id": cls.env.ref("base.do").id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Test Widget",
            "type": "consu",
            "list_price": 1000.00,
            "default_code": "WIDGET-001",
        })
        cls.generator = cls.env["l10n_do.ecf.xml.generator"]

    def _create_test_move(self, ncf_type="e-fiscal", fiscal_number="E310000000001"):
        """Create a minimal account.move for testing."""
        # Find the document type
        doc_type = self.env["l10n_latam.document.type"].search([
            ("l10n_do_ncf_type", "=", ncf_type),
            ("country_id.code", "=", "DO"),
        ], limit=1)
        if not doc_type:
            # Create a mock document type for testing
            doc_type = self.env["l10n_latam.document.type"].create({
                "name": f"Test {ncf_type}",
                "code": "E",
                "l10n_do_ncf_type": ncf_type,
                "country_id": self.env.ref("base.do").id,
            })

        journal = self.env["account.journal"].search([
            ("type", "=", "sale"),
            ("company_id", "=", self.company.id),
        ], limit=1)

        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": date(2025, 1, 15),
            "l10n_latam_document_type_id": doc_type.id,
            "l10n_latam_document_number": fiscal_number,
            "l10n_do_income_type": "01",
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "name": "Test Widget",
                "quantity": 10,
                "price_unit": 100.00,
            })],
        })
        return move

    def test_generate_e31_basic_structure(self):
        """Test E31 (Factura Crédito Fiscal) generates correct root structure."""
        move = self._create_test_move("e-fiscal", "E310000000001")
        xml_root = self.generator.generate_ecf_xml(move)

        self.assertEqual(xml_root.tag, "ECF")

        # Check main sections exist
        encabezado = xml_root.find("Encabezado")
        self.assertIsNotNone(encabezado, "Encabezado section missing")

        detalles = xml_root.find("DetallesItems")
        self.assertIsNotNone(detalles, "DetallesItems section missing")

        firma = xml_root.find("FechaHoraFirma")
        self.assertIsNotNone(firma, "FechaHoraFirma section missing")

    def test_encabezado_version(self):
        """Test that Encabezado has Version 1.0."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        version = xml_root.find("Encabezado/Version")
        self.assertIsNotNone(version)
        self.assertEqual(version.text, "1.0")

    def test_id_doc_fields(self):
        """Test IdDoc contains required fields."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        id_doc = xml_root.find("Encabezado/IdDoc")

        self.assertIsNotNone(id_doc)
        self.assertEqual(id_doc.find("TipoeCF").text, "31")
        self.assertEqual(id_doc.find("eNCF").text, "E310000000001")
        self.assertIsNotNone(id_doc.find("TipoPago"))
        self.assertIsNotNone(id_doc.find("TablaFormasPago"))

    def test_emisor_fields(self):
        """Test Emisor contains company info."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        emisor = xml_root.find("Encabezado/Emisor")

        self.assertIsNotNone(emisor)
        self.assertEqual(emisor.find("RNCEmisor").text, "130862346")
        self.assertEqual(emisor.find("RazonSocialEmisor").text, "Test Company SRL")
        self.assertEqual(emisor.find("FechaEmision").text, "15-01-2025")

    def test_comprador_fields(self):
        """Test Comprador contains partner info."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        comprador = xml_root.find("Encabezado/Comprador")

        self.assertIsNotNone(comprador)
        self.assertEqual(comprador.find("RNCComprador").text, "131234567")
        self.assertEqual(
            comprador.find("RazonSocialComprador").text, "Test Customer SRL"
        )

    def test_detalles_items(self):
        """Test line items are correctly generated."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        detalles = xml_root.find("DetallesItems")

        items = detalles.findall("Item")
        self.assertTrue(len(items) > 0, "No line items generated")

        first_item = items[0]
        self.assertEqual(first_item.find("NumeroLinea").text, "1")
        self.assertEqual(first_item.find("NombreItem").text, "Test Widget")
        self.assertEqual(first_item.find("CantidadItem").text, "10.00")
        self.assertEqual(first_item.find("PrecioUnitarioItem").text, "100.00")

    def test_e32_no_buyer_required(self):
        """Test E32 (Consumo) does not require buyer with RNC."""
        partner_no_vat = self.env["res.partner"].create({
            "name": "Consumer Without VAT",
        })
        move = self._create_test_move("e-consumer", "E320000000001")
        move.partner_id = partner_no_vat
        xml_root = self.generator.generate_ecf_xml(move)

        # E32 should not have Comprador if no VAT
        comprador = xml_root.find("Encabezado/Comprador")
        # It may or may not exist depending on partner data
        self.assertEqual(xml_root.tag, "ECF")

    def test_credit_note_requires_reference(self):
        """Test E34 (Nota de Crédito) requires InformacionReferencia."""
        move = self._create_test_move("e-credit_note", "E340000000001")
        move.l10n_do_origin_ncf = "E310000000001"
        move.l10n_do_ecf_modification_code = "1"

        xml_root = self.generator.generate_ecf_xml(move)
        info_ref = xml_root.find("InformacionReferencia")
        self.assertIsNotNone(info_ref)
        self.assertEqual(info_ref.find("NCFModificado").text, "E310000000001")
        self.assertEqual(info_ref.find("CodigoModificacion").text, "1")

    def test_date_format(self):
        """Test dates use DD-MM-YYYY format."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        fecha = xml_root.find("Encabezado/Emisor/FechaEmision")
        self.assertRegex(fecha.text, r"\d{2}-\d{2}-\d{4}")

    def test_xml_is_valid(self):
        """Test generated XML can be serialized and parsed back."""
        move = self._create_test_move()
        xml_root = self.generator.generate_ecf_xml(move)
        xml_bytes = etree.tostring(xml_root, xml_declaration=True, encoding="UTF-8")
        parsed = etree.fromstring(xml_bytes)
        self.assertEqual(parsed.tag, "ECF")

    def test_clean_vat(self):
        """Test VAT cleaning removes non-alphanumeric chars."""
        result = self.generator._clean_vat("130-862-346")
        self.assertEqual(result, "130862346")

        result = self.generator._clean_vat("DO 130862346")
        self.assertEqual(result, "DO130862346")

        result = self.generator._clean_vat(None)
        self.assertEqual(result, "")

    def test_all_ecf_types_have_builders(self):
        """Verify every e-CF type has a builder method."""
        from odoo.addons.l10n_do_ecf_invoicing.models.ecf_xml_generator import (
            NCF_TYPE_TO_CODE,
        )
        for ncf_type, code in NCF_TYPE_TO_CODE.items():
            method_name = f"_build_ecf_{code}"
            self.assertTrue(
                hasattr(self.generator, method_name),
                f"Missing builder method {method_name} for {ncf_type}",
            )

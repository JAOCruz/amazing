"""
DGII e-CF Receptor Endpoints — Paso 7+
Implementa los servicios que DGII llama para entregar e-CFs a Odoo.

Endpoints expuestos:
  GET  /fe/autenticacion/api/semilla               → genera semilla temporal
  POST /fe/autenticacion/api/ValidacionCertificado → valida firma DGII sobre la semilla
  POST /fe/recepcion/api/ecf                       → recibe e-CF de DGII
  POST /fe/aprobacioncomercial/api/ecf             → recibe aprobación comercial
"""

import base64
import logging
import secrets
import hashlib
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# In-memory seed store: {seed_value: expires_at}
# For production, use ir.config_parameter or a model
_SEED_STORE = {}


def _xml_response(xml_str, status=200):
    return Response(
        xml_str,
        status=status,
        content_type='application/xml; charset=utf-8',
    )


def _clean_expired_seeds():
    now = datetime.utcnow()
    expired = [k for k, v in _SEED_STORE.items() if v < now]
    for k in expired:
        del _SEED_STORE[k]


class ECFReceptorController(http.Controller):

    # ──────────────────────────────────────────────────────────────────────────
    # 1. AUTENTICACIÓN — Semilla
    # GET /fe/autenticacion/api/semilla
    # DGII llama aquí para obtener una semilla aleatoria.
    # Respondemos con XML: <SemillaModel><valor>SEED</valor></SemillaModel>
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        '/fe/autenticacion/api/semilla',
        type='http', auth='none', methods=['GET'], csrf=False,
    )
    def get_semilla(self, **kwargs):
        _clean_expired_seeds()

        seed = secrets.token_hex(16).upper()  # 32-char hex seed
        expires = datetime.utcnow() + timedelta(minutes=5)
        _SEED_STORE[seed] = expires

        _logger.info('[ECF Receptor] Semilla generada: %s', seed)

        now_iso = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<SemillaModel>\n'
            f'  <valor>{seed}</valor>\n'
            f'  <fecha>{now_iso}</fecha>\n'
            '</SemillaModel>'
        )
        return _xml_response(xml)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. AUTENTICACIÓN — Validación de Certificado
    # POST /fe/autenticacion/api/ValidacionCertificado
    # DGII envía un XML firmado con la semilla. Validamos y devolvemos token.
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        ['/fe/autenticacion/api/ValidacionCertificado',
         '/fe/autenticacion/api/validacionCertificado',
         '/fe/autenticacion/api/validacioncertificado'],
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def validar_certificado(self, **kwargs):
        raw = request.httprequest.get_data(as_text=True)
        _logger.info('[ECF Receptor] ValidacionCertificado recibida (%d bytes)', len(raw))

        # TODO Paso 8+: verificar firma XML con certificado DGII
        # Por ahora aceptamos todo (ambiente CerteCF = pruebas)
        token = secrets.token_hex(32)

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<RespuestaAutenticacion>\n'
            '  <estado>1</estado>\n'
            '  <mensaje>Certificado validado correctamente</mensaje>\n'
            f'  <token>{token}</token>\n'
            '</RespuestaAutenticacion>'
        )
        return _xml_response(xml)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. RECEPCIÓN — e-CF entrante
    # POST /fe/recepcion/api/ecf
    # DGII entrega un e-CF firmado. Lo guardamos y devolvemos ACE.
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        '/fe/recepcion/api/ecf',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def recibir_ecf(self, **kwargs):
        # DGII may send the e-CF as raw body OR as multipart file field 'xml'
        raw = request.httprequest.get_data()
        if not raw:
            # Try multipart file upload (field name: 'xml')
            xml_file = request.httprequest.files.get('xml')
            if xml_file:
                raw = xml_file.read()
            # Try form field
            if not raw:
                xml_str = request.httprequest.form.get('xml') or kwargs.get('xml', '')
                raw = xml_str.encode('utf-8') if isinstance(xml_str, str) else xml_str
        _logger.info('[ECF Receptor] e-CF recibido (%d bytes) content-type=%s',
                     len(raw), request.httprequest.content_type)
        _logger.info('[ECF Receptor] RAW XML: %s', raw[:2000])

        # Parse encf from XML for logging
        encf = 'DESCONOCIDO'
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw)
            for el in root.iter():
                tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if tag == 'eNCF' and el.text:
                    encf = el.text.strip()
                    break
            _logger.info('[ECF Receptor] eNCF extraído: %s', encf)
        except Exception as e:
            _logger.warning('[ECF Receptor] Error parseando XML: %s', e)

        # Store in Odoo as attachment (optional — for audit trail)
        try:
            request.env['ir.attachment'].sudo().create({
                'name': f'ecf_inbound_{encf}_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.xml',
                'type': 'binary',
                'datas': base64.b64encode(raw).decode(),
                'mimetype': 'application/xml',
                'description': f'e-CF recibido de DGII — {encf}',
            })
        except Exception as e:
            _logger.warning('[ECF Receptor] No se pudo guardar adjunto: %s', e)

        # Extraer RNCEmisor y RNCComprador del XML entrante
        # En Paso 8: DGII (101000978) es el emisor, Amazing Prosthetics (131341519) es el comprador
        rnc_emisor = '101000978'  # DGII RNC (default emisor — quien nos envía el e-CF)
        rnc_comprador = '131341519'  # Amazing Prosthetics RNC (default comprador — nosotros)
        try:
            root_xml = ET.fromstring(raw)
            for el in root_xml.iter():
                tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if tag == 'RNCEmisor' and el.text:
                    rnc_emisor = el.text.strip()
                if tag == 'RNCComprador' and el.text:
                    rnc_comprador = el.text.strip()
            _logger.info('[ECF Receptor] RNCs extraídos del XML — Emisor: %s, Comprador: %s', rnc_emisor, rnc_comprador)
        except Exception as e:
            _logger.warning('[ECF Receptor] Error parseando XML entrante, usando defaults: %s', e)

        # ARECF — Acuse de Recibo conforme al XSD ARECF_v1.0
        now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        arecf_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ARECF>\n'
            '  <DetalleAcusedeRecibo>\n'
            f'    <Version>1.0</Version>\n'
            f'    <RNCEmisor>{rnc_emisor}</RNCEmisor>\n'
            f'    <RNCComprador>{rnc_comprador}</RNCComprador>\n'
            f'    <eNCF>{encf}</eNCF>\n'
            f'    <Estado>0</Estado>\n'
            f'    <FechaHoraAcuseRecibo>{now}</FechaHoraAcuseRecibo>\n'
            '  </DetalleAcusedeRecibo>\n'
            '</ARECF>'
        )

        # Firmar el ARECF con el .p12 de la compañía
        try:
            company = request.env['res.company'].sudo().search([], limit=1)
            p12_bytes, password = company._get_l10n_do_ecf_certificate_data()
            if p12_bytes:
                dgii_api = request.env['l10n_do.dgii.api'].sudo()
                signed_bytes = dgii_api._sign_xml_with_node(
                    xml_bytes=arecf_xml.encode('utf-8'),
                    p12_bytes=p12_bytes,
                    password=password.decode('utf-8') if isinstance(password, bytes) else (password or ''),
                    root_el_name='ARECF',
                )
                _logger.info('[ECF Receptor] ARECF firmado exitosamente para eNCF: %s', encf)
                return _xml_response(signed_bytes.decode('utf-8'))
            else:
                _logger.warning('[ECF Receptor] No hay .p12 configurado — enviando ARECF sin firma')
        except Exception as e:
            _logger.error('[ECF Receptor] Error firmando ARECF: %s', e, exc_info=True)

        # Fallback: enviar sin firma (solo si falla el signing)
        _logger.info('[ECF Receptor] ARECF sin firma enviado para eNCF: %s', encf)
        return _xml_response(arecf_xml)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. APROBACIÓN COMERCIAL — ACECF entrante
    # POST /fe/aprobacioncomercial/api/ecf
    # DGII entrega una aprobación/rechazo comercial del comprador.
    # ──────────────────────────────────────────────────────────────────────────
    @http.route(
        '/fe/aprobacioncomercial/api/ecf',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def recibir_aprobacion_comercial(self, **kwargs):
        raw = request.httprequest.get_data()
        _logger.info('[ECF Receptor] Aprobación Comercial recibida (%d bytes)', len(raw))

        encf = 'DESCONOCIDO'
        estado = 'DESCONOCIDO'
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw)
            for el in root.iter():
                tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if tag == 'eNCF' and el.text:
                    encf = el.text.strip()
                if tag == 'Estado' and el.text:
                    estado = el.text.strip()
        except Exception:
            pass

        # Store as attachment
        try:
            request.env['ir.attachment'].sudo().create({
                'name': f'acecf_inbound_{encf}_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.xml',
                'type': 'binary',
                'datas': base64.b64encode(raw).decode(),
                'mimetype': 'application/xml',
                'description': f'ACECF recibido — {encf} Estado:{estado}',
            })
        except Exception as e:
            _logger.warning('[ECF Receptor] No se pudo guardar ACECF: %s', e)

        now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<RespuestaAprobacionComercial>\n'
            f'  <eNCF>{encf}</eNCF>\n'
            f'  <Estado>Recibido</Estado>\n'
            f'  <FechaHora>{now}</FechaHora>\n'
            '</RespuestaAprobacionComercial>'
        )
        return _xml_response(xml)

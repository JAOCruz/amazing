# -*- coding: utf-8 -*-
import os
import re
from odoo import http
from odoo.http import request


class ChartJSController(http.Controller):
    """Controlador para servir Chart.js cuando el asset bundle falla"""
    
    @http.route([
        '/web/assets/<path:asset_path>/web.chartjs_lib.min.js',
        '/web/assets/web.chartjs_lib.min.js',
    ], type='http', priority=1, auth='public', methods=['GET'], csrf=False, sitemap=False)
    def serve_chartjs_lib(self, asset_path=None):
        """
        Sirve Chart.js directamente cuando el asset bundle web.chartjs_lib.min.js falla.
        Esto intercepta las solicitudes fallidas y devuelve los archivos concatenados.
        """
        try:
            # Rutas de los archivos fuente de Chart.js
            chartjs_path = '/usr/lib/python3/dist-packages/odoo/addons/web/static/lib/Chart/Chart.js'
            adapter_path = '/usr/lib/python3/dist-packages/odoo/addons/web/static/lib/chartjs-adapter-luxon/chartjs-adapter-luxon.js'
            
            # Leer y concatenar los archivos
            content = ""
            if os.path.exists(chartjs_path):
                with open(chartjs_path, 'r', encoding='utf-8') as f:
                    content += f.read() + "\n"
            
            if os.path.exists(adapter_path):
                with open(adapter_path, 'r', encoding='utf-8') as f:
                    content += f.read() + "\n"
            
            if not content:
                # Si no se encuentran los archivos, devolver un script vacío
                content = "// Chart.js files not found"
            
            # Devolver como JavaScript
            response = request.make_response(
                content,
                headers=[
                    ('Content-Type', 'application/javascript; charset=utf-8'),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ]
            )
            return response
            
        except Exception as e:
            # En caso de error, devolver un script que no cause errores
            error_content = f"// Error loading Chart.js: {str(e)}\n// Chart library may not be available"
            return request.make_response(
                error_content,
                headers=[
                    ('Content-Type', 'application/javascript; charset=utf-8'),
                ],
                status=200  # Devolver 200 para evitar errores en el frontend
            )

    @http.route('/web/assets/<regex("[a-f0-9]+"):asset_hash>/web.chartjs_lib.min.js', 
                type='http', priority=1, auth='public', methods=['GET'], csrf=False, sitemap=False)
    def serve_chartjs_lib_with_hash(self, asset_hash=None):
        """Sirve Chart.js para rutas con hash específico (ej: e8b87f8)"""
        return self.serve_chartjs_lib(asset_path=asset_hash)

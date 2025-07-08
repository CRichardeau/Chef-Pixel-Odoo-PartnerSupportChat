from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class ValidateKeyController(http.Controller):

    @http.route('/api/validate_key', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_api_key(self):
        data = json.loads(request.httprequest.data.decode('utf-8'))
        _logger.info(f"API validation request data: {data}")

        api_key = data.get("api_key")
        db = data.get("database")

        if not api_key or not db:
            return {"success": False, "message": "Missing API key or database name"}

        record = request.env['client.support.bridge'].sudo().search([('token', '=', api_key),
                                                                     ('client_db', '=', db)], limit=1)
        if record:
            return {"success": True, "message": "Valid API key", "database": db}
        else:
            return {"success": False, "message": "Invalid API key"}
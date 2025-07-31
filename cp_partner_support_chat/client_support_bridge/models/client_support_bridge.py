# -*- coding: utf-8 -*-

import uuid
import logging
import requests
import json
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ClientSupportBridge(models.Model):
    _name = 'client.support.bridge'
    _inherit = ['mail.activity.mixin', 'mail.thread']
    _description = 'Client Support Bridge'

    name = fields.Char("Session Name", required=True, tracking=True)
    client_db = fields.Char("Client Database", required=True, tracking=True)
    client_user = fields.Char("Client User")
    client_company = fields.Char("Client Company")
    token = fields.Char("Security Token", readonly=True, copy=False)
    livechat_channel_id = fields.Many2one('im_livechat.channel',
                                          string="Livechat Channel",
                                          default=lambda self: self.env.ref(
                                              'client_support_bridge.client_livechat_channel', False))
    mail_channel_id = fields.Many2one('discuss.channel', "Chat Channel")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], default='draft')
    client_url = fields.Char("Client URL", required=True, tracking=True)
    client_channel = fields.Char("Client Channel")
    authorized_client_ids = fields.One2many('client.support.authorized', 'bridge_id', string="Authorized Clients")

    def create(self, vals):
        vals['token'] = str(uuid.uuid4())
        return super(ClientSupportBridge, self).create(vals)

    def test_client_connection(self):
        """Test connection to client system via API key"""
        client_url = self.client_url
        client_db = self.client_db
        partner_db = self.env.cr.dbname
        api_key = self.token
        test_url = f"{client_url}/api/client_validate_key"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            'api_key': api_key,
            'database': partner_db
        }

        try:
            response = requests.post(
                test_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            result = response.json()
            if result:
                result = result['result']

            if response.status_code == 200:
                if result.get('success'):
                    self.sudo().write({'state': 'active'})
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Test'),
                            'message': _('Successfully connected to client: %s') % result.get('database', client_db),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Test'),
                            'message': _('Failed to connect, partner response: %s') % result.get('message'),
                            'type': 'warning',
                            'sticky': False,
                        }
                    }

            raise UserError(_("Failed to connect. HTTP status: %s") % response.status_code)

        except Exception as e:
            _logger.exception("Connection test failed")
            raise UserError(_("Connection test failed: %s") % str(e))

    def initialize_chat_session(self, client_user_id, client_user_name, client_company_name, client_channel,
                                partner_session, support_users):
        """Create a new mail.channel for the incoming client request"""
        partner_obj = self.env['res.partner'].sudo()
        operator_partner = False

        client_company_partner = partner_obj.search([
            ('name', '=', client_company_name)], limit=1)
        if not client_company_partner:
            client_company_partner = partner_obj.create({
                'name': client_company_name,
                'company_type': 'company'
            })
            operator_partner = partner_obj.search([
                ('name', '=', client_user_name),
                ('parent_id', '=', client_company_partner.id)
            ], limit=1)
            if not operator_partner:
                operator_partner = partner_obj.create({
                    'name': client_user_name,
                    'company_type': 'person',
                    'parent_id': client_company_partner.id,
                })
        if operator_partner:
            operator = operator_partner
        else:
            operator = self.livechat_channel_id.available_operator_ids[
                0].partner_id if self.livechat_channel_id.available_operator_ids else False
        if not operator:
            return {'error': 'No operators available'}

        partner_ids = [user.partner_id.id for user in support_users]
        channel_partner_ids = [(4, pid) for pid in partner_ids]
        if operator_partner:
            channel_partner_ids.append((4, operator_partner.id))

        # Create mail channel - reusing livechat code
        mail_channel = self.env['discuss.channel'].sudo().with_context(mail_create_nosubscribe=True).create({
            'channel_partner_ids': channel_partner_ids,
            'livechat_channel_id': self.livechat_channel_id.id,
            'livechat_operator_id': operator.id if operator else False,
            'channel_type': 'channel',
            'name': f"Support: {client_company_name} - {client_user_name}",
            'client_channel_id': client_channel,
            'client_connector_id': self.id,
            'group_public_id': False,
            'group_ids': [(6, 0, [])]
        })

        for member in mail_channel.channel_member_ids:
            member.write({
                'custom_notifications': 'all',
                'fold_state': 'open'
            })

        # Update bridge record
        self.sudo().write({
            # 'mail_channel_id': mail_channel.id,
            # 'state': 'active',
            # 'client_user': client_user_name,
            'client_company': client_company_name,
            'client_channel': client_channel,
            'authorized_client_ids': [(0, 0, {
                'client_user': client_user_name,
                'channel_id': mail_channel.id,
                'date': fields.Datetime.now(),
                'state': 'active',
                'partner_session': partner_session,
                'client_channel': client_channel
            })]
        })

        return {
            'channel_id': mail_channel.id,
            'operator_id': operator.id if operator else False,
            'operator_name': operator.name if operator else 'Support Agent',
            'partner_company': self.env.company.name
        }

    def close_chat_session(self, partner_session):
        """
        close the chat with client
        """
        authorized_client = self.authorized_client_ids.filtered(lambda x: x.partner_session == partner_session)
        if authorized_client:
            authorized_client.sudo().write({'state': 'close'})


class ClientSupportAuthorized(models.Model):
    _name = 'client.support.authorized'
    _description = 'Authorized Client'

    bridge_id = fields.Many2one('client.support.bridge', required=True, ondelete='cascade')
    client_db = fields.Char("Database Name", copy=False)
    client_user = fields.Char("Client User", copy=False)
    api_key = fields.Char("API Key", copy=False)
    is_active = fields.Boolean("Active", default=True)
    channel_id = fields.Many2one('discuss.channel', string='Chat Channel', copy=False)
    date = fields.Datetime("Timestamp", copy=False)
    state = fields.Selection([
        ('active', 'Active'),
        ('close', 'Closed')
    ], string='Chat Status', copy=False)
    partner_session = fields.Integer(string='Partner Session', copy=False)
    client_channel = fields.Integer("Client Channel", copy=False)

    def open_discuss_channel(self):
        """
        open the discuss channel
        """
        return {
            'type': 'ir.actions.act_url',
            'url': f'odoo/discuss?active_id=discuss.channel_{self.channel_id.id}',
            'target': 'self',
        }

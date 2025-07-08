# -*- coding: utf-8

import requests
import json
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class PartnerSupportSession(models.Model):
    _name = 'partner.support.session'
    _description = 'Partner Support Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char("Session Name", required=True, tracking=True)
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user.id, readonly=True)
    connector_id = fields.Many2one('partner.support.connector', 'Support Connector', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], default='draft', tracking=True)
    partner_channel_id = fields.Char("Partner Channel ID", copy=False)
    livechat_channel_id = fields.Many2one('im_livechat.channel',
                                          string="Livechat Channel", copy=False)
    mail_channel_id = fields.Many2one('discuss.channel', "Chat Channel", copy=False)
    operator_name = fields.Char("Operator Name", copy=False)

    def initiate_support_chat(self):
        """Initiate a chat with partner support"""
        if not self.connector_id or self.state != 'draft':
            return False

        # Prepare request data
        company = self.env.company
        data = {
            'db_name': self.env.cr.dbname,
            'api_key': self.connector_id.api_key,
            'user_id': self.user_id.id,
            'user_name': self.user_id.name,
            'company_name': company.name,
            'partner_session': self.id
        }

        # Make API call to partner
        try:
            url = f"{self.connector_id.partner_url}/client_support/initiate"
            headers = {'Content-type': 'application/json'}

            # create discuss channel
            mail_channel = self.env['discuss.channel'].sudo().with_context(mail_create_nosubscribe=True).create({
                'channel_partner_ids': [(4, self.user_id.partner_id.id)],
                'livechat_channel_id': self.livechat_channel_id.id,
                'livechat_operator_id': self.user_id.partner_id.id,
                'channel_type': 'channel',
                'name': f"Partner Support: {self.name} - {self.user_id.name}",
                'support_session_id': self.id,
                'group_public_id': False,
                'group_ids': [(6, 0, [])]
            })
            for member in mail_channel.channel_member_ids:
                member.write({
                    'custom_notifications': 'all'
                })

            data['client_channel'] = mail_channel.id
            print('\n--data--->', data)
            response = requests.post(url, data=json.dumps(data), headers=headers)
            result = response.json()
            if result:
                result = result['result']

            if 'error' in result:
                _logger.error(f"Failed to initiate support chat: {result['error']}")
                return False

            partner_channel = result.get('channel_id')

            mail_channel.write({'partner_channel_id': partner_channel})

            # Update session with partner info
            self.sudo().write({
                'state': 'active',
                'partner_channel_id': partner_channel,
                'operator_name': result.get('operator_name', 'Support Agent'),
                'mail_channel_id': mail_channel.id
            })

            # Post system message to the chatter
            self.message_post(
                body=f"Connected to support operator: {result.get('operator_name', 'Support Agent')}",
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )

            # Redirect to mail channel
            return {
                'type': 'ir.actions.act_url',
                'url': f'odoo/discuss?active_id=discuss.channel_{mail_channel.id}',
                'target': 'self',
            }

        except Exception as e:
            _logger.error(f"Error initiating support chat: {str(e)}")
            return False

    def send_message(self, message):
        """Send message to partner support"""
        if not self.connector_id or self.state != 'active':
            return False

        # Prepare message data
        data = {
            'db_name': self.env.cr.dbname,
            'api_key': self.connector_id.api_key,
            'message': message,
            'user_name': self.user_id.name
        }

        # Make API call to partner
        try:
            url = f"{self.connector_id.partner_url}/client_support/message"
            headers = {'Content-type': 'application/json'}
            response = requests.post(url, data=json.dumps(data), headers=headers)
            result = response.json()

            if 'error' in result:
                _logger.error(f"Failed to send message: {result['error']}")
                return False

            # Post message to the chatter
            self.message_post(
                body=f"<p><strong>You:</strong> {message}</p>",
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

            return True

        except Exception as e:
            _logger.error(f"Error sending message: {str(e)}")
            return False

    def open_discuss_channel(self):
        """
        open the discuss channel
        """
        if self.mail_channel_id:
            return {
                'type': 'ir.actions.act_url',
                'url': f'odoo/discuss?active_id=discuss.channel_{self.mail_channel_id.id}',
                'target': 'self',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Open Chat',
                    'message': 'Once the you start the chat then you can open it.',
                    'type': 'danger',
                }
            }

    def close_session(self):
        if self.state != 'active':
            return False

        # Prepare request data
        company = self.env.company
        data = {
            'db_name': self.env.cr.dbname,
            'api_key': self.connector_id.api_key,
            'partner_session': self.id
        }

        # Make API call to partner
        url = f"{self.connector_id.partner_url}/client_support/close_chat"
        headers = {'Content-type': 'application/json'}
        response = requests.post(url, data=json.dumps(data), headers=headers)
        self.sudo().write({
            'state': 'closed'
        })

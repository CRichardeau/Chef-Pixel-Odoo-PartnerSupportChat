# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    client_channel_id = fields.Char(string="Client Channel ID", copy=False)
    client_connector_id = fields.Many2one('client.support.bridge', string="Client Connector")
    is_partner_communicate = fields.Boolean("Is Partner Communicate", default=False, copy=False)

    def _message_post_after_hook(self, message, msg_vals):
        super(DiscussChannel, self)._message_post_after_hook(message, msg_vals)

        if self.env.context.get('from_bridge'):
            return

        if (self.client_channel_id or self.client_connector_id.client_channel) and self.client_connector_id:
            if not self.is_partner_communicate:
                # for member in self.channel_member_ids.filtered(lambda x: x.partner_id != self.env.user.partner_id):
                #     member.write({
                #         'custom_notifications': 'no_notif',
                #         'fold_state': 'closed'
                #     })
                self.channel_partner_ids = [(6, 0, [self.env.user.partner_id.id])]
            self.is_partner_communicate = True

            message_data = {
                'channel_id': self.client_channel_id or self.client_connector_id.client_channel,
                'body': message.body,
                'author_id': {
                    'id': message.author_id.id,
                    'name': message.author_id.name,
                },
                'message_type': 'comment',
                'partner_ids': [(4, self.env.user.partner_id.id)],
                'is_one_partner_talk': True
            }

            headers = {'Content-Type': 'application/json'}
            try:
                response = requests.post(
                    f"{self.client_connector_id.client_url}/partner_support_connector/receive_message",
                    data=json.dumps(message_data),
                    headers=headers
                )
                
                if response.status_code != 200:
                    _logger.error("Failed to send message to client: %s", response.text)

            except Exception as e:
                _logger.error("Error sending message to client: %s", str(e))

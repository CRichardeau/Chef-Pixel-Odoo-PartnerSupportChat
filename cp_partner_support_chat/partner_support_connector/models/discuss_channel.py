# -*- coding: utf-8 -*-

from odoo import models, fields
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    partner_channel_id = fields.Char(string="Partner Channel ID", copy=False)
    support_session_id = fields.Many2one('partner.support.session', string="Partner Support Session", copy=False)

    def _message_post_after_hook(self, message, msg_vals):
        print('\n Partner module -_message_post_after_hook--->', self, self._context)
        super(DiscussChannel, self)._message_post_after_hook(message, msg_vals)

        if self.env.context.get('to_bridge'):
            return

        if (self.partner_channel_id or self.support_session_id.partner_channel_id) and self.support_session_id:

            message_data = {
                'channel_id': self.partner_channel_id or self.support_session_id.partner_channel_id,
                'body': message.body,
                'author_id': {
                    'id': message.author_id.id,
                    'name': message.author_id.name,
                },
                'message_type': 'comment',
                'partner_ids': [(4, self.env.user.partner_id.id)],
            }
            print('\n--message_data--->', message_data)

            headers = {'Content-Type': 'application/json'}
            try:
                response = requests.post(
                    f"{self.support_session_id.connector_id.partner_url}/client_support_bridge/receive_message",
                    data=json.dumps(message_data),
                    headers=headers
                )

                if response.status_code != 200:
                    _logger.error("Failed to send message to client: %s", response.text)

            except Exception as e:
                _logger.error("Error sending message to client: %s", str(e))

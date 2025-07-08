from odoo import models, fields
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    client_channel_id = fields.Char(string="Client Channel ID", copy=False)
    client_connector_id = fields.Many2one('client.support.bridge', string="Client Connector")

    def _message_post_after_hook(self, message, msg_vals):
        print('\n client module -_message_post_after_hook--->', self, self._context, self.client_channel_id, self.client_connector_id.client_channel)
        super(DiscussChannel, self)._message_post_after_hook(message, msg_vals)

        if self.env.context.get('from_bridge'):
            return

        if (self.client_channel_id or self.client_connector_id.client_channel) and self.client_connector_id:
            
            message_data = {
                'channel_id': self.client_channel_id or self.client_connector_id.client_channel,
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
                    f"{self.client_connector_id.client_url}/partner_support_connector/receive_message",
                    data=json.dumps(message_data),
                    headers=headers
                )
                
                if response.status_code != 200:
                    _logger.error("Failed to send message to client: %s", response.text)

            except Exception as e:
                _logger.error("Error sending message to client: %s", str(e))

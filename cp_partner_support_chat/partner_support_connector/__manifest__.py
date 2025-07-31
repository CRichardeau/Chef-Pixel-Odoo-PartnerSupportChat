# -*- coding: utf-8 -*-

{
    "name": "Partner Support Connector",
    "summary": "Module used to connect with the partners.",
    "description": "Module used to connect with the partners.",
    "version": "18.0",
    "category": "Discuss",
    "author": "CHEF PIXEL",
    "website": "https://chef-pixel.fr",
    "support": "hello@chef-pixel.fr",
    "depends": ["base", "mail", "im_livechat", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/partner_support_connector_view.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}

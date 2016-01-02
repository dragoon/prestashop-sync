#!/bin/sh

ln -s /var/www/prestashop-sync/config/supervisor.conf /etc/supervisor/conf.d/prestashop-sync.conf
ln -s /var/www/prestashop-sync/config/nginx.conf /etc/nginx/sites-available/prestashop-sync
ln -s /etc/nginx/sites-available/prestashop-sync /etc/nginx/sites-enabled/prestashop-sync

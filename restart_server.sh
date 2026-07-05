#!/bin/bash
cd /opt/fire-inspect/backend
/usr/local/bin/pm2 restart fire-inspect
sleep 2
/usr/local/bin/pm2 logs fire-inspect --err --lines 10 --nostream

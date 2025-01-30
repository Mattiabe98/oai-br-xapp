#/bin/bash
cd /root/oai-xapp/
git pull
helm dependency update
helm uninstall oai-xapp
sleep 2
helm install oai-xapp .

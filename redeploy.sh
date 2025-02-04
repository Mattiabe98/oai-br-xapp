#/bin/bash
cd /root/oai-br-xapp/
git pull
helm dependency update
helm uninstall oai-br-xapp
sleep 2
helm install oai-br-xapp .

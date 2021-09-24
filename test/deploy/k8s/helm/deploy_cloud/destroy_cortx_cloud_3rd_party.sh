#!/bin/bash

PVC_CONSUL_FILTER="data-default-consul"
PVC_KAFKA_FILTER="kafka"
PVC_ZOOKEEPER_FILTER="zookeeper"
PV_FILTER="pvc"

printf "###################################\n"
printf "# Delete Kafka                    #\n"
printf "###################################\n"
helm uninstall kafka

printf "###################################\n"
printf "# Delete Zookeeper                #\n"
printf "###################################\n"
helm uninstall zookeeper

printf "###################################\n"
printf "# Delete openLDAP                 #\n"
printf "###################################\n"
kubectl delete -f open-ldap-deployment.yaml
kubectl delete -f open-ldap-svc.yaml

printf "###################################\n"
printf "# Delete Consul                   #\n"
printf "###################################\n"
helm delete consul
kubectl delete -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

printf "###################################\n"
printf "# Delete Persistent Volume Claims #\n"
printf "###################################\n"
VOLUME_CLAIMS=$(kubectl get pvc | grep -E "$PVC_CONSUL_FILTER|$PVC_KAFKA_FILTER|$PVC_ZOOKEEPER_FILTER" | cut -f1 -d " ")
echo $VOLUME_CLAIMS
for VOLUME_CLAIM in $VOLUME_CLAIMS
do
    printf "Removing $VOLUME_CLAIM\n"
    kubectl delete pvc $VOLUME_CLAIM
done

printf "###################################\n"
printf "# Delete Persistent Volumes       #\n"
printf "###################################\n"
PERSISTENT_VOLUMES=$(kubectl get pv | grep -E "$PVC_CONSUL_FILTER|$PVC_KAFKA_FILTER|$PVC_ZOOKEEPER_FILTER" | cut -f1 -d " ")
echo $PERSISTENT_VOLUMES
for PERSISTENT_VOLUME in $PERSISTENT_VOLUMES
do
    printf "Removing $PERSISTENT_VOLUME\n"
    kubectl delete pv $PERSISTENT_VOLUME
done
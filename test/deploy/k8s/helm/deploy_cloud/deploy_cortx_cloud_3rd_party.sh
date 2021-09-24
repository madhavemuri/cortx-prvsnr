#!/bin/bash
STORAGE_CLASS=${1:-'local-path'}
NUM_WORKER_NODES=${2:-2}
printf "STORAGE_CLASS = $STORAGE_CLASS\n"
printf "NUM_WORKER_NODES = $NUM_WORKER_NODES\n"


printf "###############################\n"
printf "# Deploy Consul               #\n"
printf "###############################\n"

# Add the HashiCorp Helm Repository:
helm repo add hashicorp https://helm.releases.hashicorp.com
if [[ $STORAGE_CLASS == "local-path" ]]
then
    printf "Install Rancher Local Path Provisioner"
    # Install Rancher provisioner
    kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
fi
# Set default StorageClass
kubectl patch storageclass $STORAGE_CLASS -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

helm install consul hashicorp/consul --set global.name=consul,server.storageClass=$STORAGE_CLASS,server.replicas=$NUM_WORKER_NODES

printf "###############################\n"
printf "# Deploy openLDAP             #\n"
printf "###############################\n"
kubectl create secret generic openldap \
    --from-literal=adminpassword=adminpassword \
    --from-literal=users=user01,user02 \
    --from-literal=passwords=password01,password02
kubectl create -f open-ldap-svc.yaml
kubectl create -f open-ldap-deployment.yaml
kubectl scale -f open-ldap-deployment.yaml --replicas=$NUM_WORKER_NODES

printf "###############################\n"
printf "# Deploy Zookeeper            #\n"
printf "###############################\n"
# Add Zookeeper and Kafka Repository
helm repo add bitnami https://charts.bitnami.com/bitnami

helm install zookeeper bitnami/zookeeper \
    --set replicaCount=$NUM_WORKER_NODES \
    --set auth.enabled=false \
    --set allowAnonymousLogin=true

printf "###############################\n"
printf "# Deploy Kafka                #\n"
printf "###############################\n"
helm install kafka bitnami/kafka \
    --set zookeeper.enabled=false \
    --set replicaCount=$NUM_WORKER_NODES \
    --set externalZookeeper.servers=zookeeper.default.svc.cluster.local
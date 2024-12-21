#!/bin/bash


# Crée les dossiers logs et plots pour les logs et les graphiques
mkdir -p logs
mkdir -p plots

# Supprime les fichiers de logs et les graphiques s'ils existent
rm -r -f plots/*
echo "" > logs/mongodb.log
echo "" > logs/mongodb-tests.log
echo "" > logs/mysql.log
echo "" > logs/mysql-tests.log

############# Installation des dépendances python ############
pip3 install -r requirements/generate_data-requirements.txt
pip3 install -r requirements/mongo-requirements.txt
pip3 install -r requirements/mysql-requirements.txt

################### Génération des données ###################
python3 generate_data.py 						&&
docker compose down -v --remove-orphans 		&&
#
#################### MongoDB ###################
####### Test en standalone ######
## Démarrage et attente de la disponibilité du serveur
docker compose up mongo-standalone -d --wait 	&&
python3 mongodb.py --standalone 				&&
docker compose down -v --remove-orphans 		&&

####### Test avec replica ######
docker compose up mongo-replica-initiate 		&&
python3 mongodb.py --replica 					&&
docker compose down -v --remove-orphans 		&&

####### Test avec sharding ######
docker compose up mongo-sharded-cluster 		&&
python3 mongodb.py --sharded 					&&
docker compose down -v --remove-orphans 		&&

################### MySQL ###################

###### Test en standalone ######
# Démarrage et attente de la disponibilité du serveur
docker compose up --wait -d mysql-standalone 	&&
python3 mysql.py --standalone 					&&
docker compose down -v --remove-orphans 		&&

###### Test avec sharding ######
docker compose up mysql-sharded-initiate 		&&
python3 mysql.py --sharded						&&
docker compose down -v --remove-orphans

Afin de reproduire les tests de performance, il faut d'abord cloner le dépôt git suivant:  
```bash
git clone https://github.com/BJCode-git/Projet-TDLE.git -b main &&
cd Projet-TDLE
```

Il faut ensuite générer les données de test en utilisant les commandes suivantes:  

```bash
pip3 install -r requirements/data_generation-requirements.txt &&
python3 data_generation.py
```

Dès lors, il faudra déployer les conteneurs docker nécessaires pour les tests de performance.  
Cela nécessite l'installation de [docker]{https://docs.docker.com/engine/install/} et de [docker compose]{https://docs.docker.com/compose/install/}.  
Plusieurs conteneurs docker sont nécessaires pour les tests de performance.
On déploie donc des conteneurs pour réaliser des tests de performance sur une base de données mongodb standalone, une base de données mongodb répliquée et une base de données mongodb sharded.
Pour déployer les conteneurs docker, il faut utiliser la commande suivante:
```bash
docker compose build mongo-standalone mongo-replica-initiate mongo-sharded-initiate && 
docker compose up -d mongo-standalone mongo-replica-initiate mongo-sharded-initiate &&
```

On réalise ensuite les tests de performance de mongodb en utilisant les commandes suivantes:
```bash
pip3 install -r requirements/mongodb-requirements.txt &&
python3 mongodb.py
```

Afin de mener les tests de performance de MySQL, il faut d'abord déployer les conteneurs docker nécessaires.  
Pour cela, il faut utiliser la commande suivante:  	
```bash
docker compose build mysql-standalone mysql-replica-initiate 
docker compose up -d mysql-standalone mysql-replica-initiate
```

On mène ensuite les tests de performance de MySQL en utilisant les commandes suivantes:
```bash
pip3 install -r requirements/mysql-requirements.txt &&
python3 mysql.py
```

Pour automatiser les tests de performance, on peut utiliser le script `run_tests.sh` qui permet de réaliser les tests de performance de mongodb et de MySQL.  
Il est également possible d'utiliser docker compose avec les commandes suivantes pour réaliser les tests de performance de mongodb et de MySQL:
```bash
docker compose build performance-tests &&
docker compose up performance-tests
```

Pour nettoyer les conteneurs docker, il faut utiliser la commande suivante:
```bash
docker compose down
docker compose down -v
```

Note : Il est possible de configurer les paramètres des tests et le déploiement en modifiant les variables disponibles dans le fichier .env


Afin de réaliser les tests de performance, il faut d'abord cloner le dépôt git suivant:

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
Pour cela, il faut d'abord installer docker et utiliser docker compose.
Pour installer docker, il faut suivre les instructions suivantes: https://docs.docker.com/engine/install/ .
Pour installer docker compose, il faut suivre les instructions suivantes: https://docs.docker.com/compose/install/ .
Plusieurs conteneurs docker sont nécessaires pour les tests de performance.
On déploie donc des conteneurs pour réaliser des tests de performance sur une base de données mongodb standalone, une base de données mongodb répliquée et une base de données mongodb sharded.
Pour déployer les conteneurs docker, il faut utiliser la commande suivante:
```bash
docker-compose build mongo-standalone mongo-replica-initiate mongo-sharded-initiate && 
docker-compose up -d mongo-standalone mongo-replica-initiate mongo-sharded-initiate &&
```

On mène ensuite les tests de performance de mongodb en utilisant les commandes suivantes:
```bash
pip3 install -r requirements/mongodb-requirements.txt &&
python3 mongodb.py
```

Pour les tests de performance de MySQL, il faut d'abord déployer les conteneurs docker nécessaires.
Pour cela, il faut utiliser la commande suivante:
```bash
docker-compose build mysql-standalone mysql-replica-initiate 
docker-compose up -d mysql-standalone mysql-replica-initiate
```

On mène ensuite les tests de performance de MySQL en utilisant les commandes suivantes:
```bash
pip3 install -r requirements/mysql-requirements.txt &&
python3 mysql.py
```



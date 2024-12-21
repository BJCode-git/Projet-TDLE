# Projet TDLE - Tests de performance de MongoDB et MySQL 

Le projet nécessite l'installation de :
 - [python3](https://www.python.org/downloads/)
 -  [pip3](https://pip.pypa.io/en/stable/installation/)
 - [docker](https://docs.docker.com/engine/install/)
 - [docker compose](https://docs.docker.com/compose/install/)
  
Ces outils permettent d'installer les dépendances des codes python et de réaliser les tests de performance de MongoDB et MySQL.
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

On déploie alors des conteneurs docker pour réaliser des tests de performance sur une base de données mongodb standalone, une base de données mongodb répliquée et une base de données mongodb fragmentée.  
Pour MySQL, on réalise des tests de performance sur une base de données standalone et une base de données fragmentée.

Il  est possible d'utiliser le script **start.sh** pour déployer automatiquement les conteneurs, lancer tous les test puis arrêter les conteneurs. Cette approche permet de réaliser les tests de performance de manière automatique et permet de consommer moins de ressources mémoire et CPU.  

```bash
chmod +x start.sh &&
./start.sh
```

Le script **start.sh** réalise basiquement les opérations suivantes:
 - Nettoyage de l'environnement
 - Crée les dossiers logs et plots pour les logs et les graphiques
  - Installation des dépendances python
 - Génération des données de test
 - Test de performance de MongoDB en standalone
 - Test de performance de MongoDB en réplication
 - Test de performance de MongoDB en sharding
 - Test de performance de MySQL en standalone
 - Test de performance de MySQL en sharding

*Installation des dépendances python :*  

```bash
pip3 install -r requirements/generate_data-requirements.txt
pip3 install -r requirements/mongo-requirements.txt
pip3 install -r requirements/mysql-requirements.txt
```
*Génération des données :*  

```bash
python3 generate_data.py 						&&
docker compose down -v --remove-orphans 		&&
```

## Tests de performance de MongoDB 

*Test en standalone :*  

```bash
## Démarrage et attente de la disponibilité du serveur
docker compose up mongo-standalone -d --wait 	&&
python3 mongodb.py --standalone 				&&
docker compose down -v --remove-orphans 		
```

*Test avec replica :*  

```bash
docker compose up mongo-replica-initiate 		&&
python3 mongodb.py --replica 					&&
docker compose down -v --remove-orphans 		
```

*Test avec sharding :*  

```bash
docker compose up mongo-sharded-cluster 		&&
python3 mongodb.py --sharded 					&&
docker compose down -v --remove-orphans 		
```

## Tests de performance de MySQL

*Test en standalone :*  

```bash
# Démarrage et attente de la disponibilité du serveur
docker compose up --wait -d mysql-standalone 	&&
python3 mysql.py --standalone 					&&
docker compose down -v --remove-orphans 		
```

*Test avec sharding :*  

```bash
docker compose up mysql-sharded-initiate 		&&
python3 mysql.py --sharded 						&&
docker compose down -v --remove-orphans
```

Il est également possible de séparer les test de performance de MongoDB et MySQL.
Après génération des données, on peut lancer toutes les infrastructures MongoDB et lancer les tests de performance de MongoDB en utilisant les commandes suivantes:  

```bash
docker compose up start_mongo &&
python3 mongodb.py
```

On peut ensuite stopper les conteneurs docker en utilisant la commande suivante:  

```bash
docker compose down -v --remove-orphans
```

On peut en faire de même avec MySQL :  

```bash
docker compose up start_mysql &&
python3 mysql.py
```

Finalement, Pour nettoyer les données générées, on peut utiliser le script **clear.sh**:  

```bash
./clear.sh
```


Note : Il est possible de configurer les paramètres des tests et le déploiement en modifiant les variables disponibles dans le fichier .env


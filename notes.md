MySQL vs MongoDB


Présentation du système NoSQL choisi : MongoDB

MongoDB est un système de gestion de bases de données NoSQL orienté documents. 
Contrairement aux bases de données relationnelles qui utilisent des tables et des schémas fixes, MongoDB stocke les données sous forme de documents JSON (JavaScript Object Notation) ou BSON (Binary JSON), ce qui offre une grande flexibilité en termes de structure des données. 
Contrairement aux bases de données relationnelles, les champs des documents d'une collection sont libres et peuvent être différents d'un document à un autre. Le seul champ commun est obligatoire est le champ "_id".
Néanmoins pour que la base soit maintenable, il est préférable d'avoir dans une collection des documents de même type
MongoDB est largement adopté pour sa capacité à gérer des données semi-structurées ou non structurées tout en offrant des performances élevées et une grande scalabilité horizontale.


Les principales caractéristiques de MongoDB incluent :

Stockage orienté documents : Les données sont regroupées en collections, chaque document étant un objet JSON avec une structure flexible.
Requêtes riches : MongoDB permet des requêtes complexes incluant des opérations d’agrégation et des jointures.
Scalabilité horizontale : Avec la fragmentation (sharding), les données peuvent être réparties sur plusieurs nœuds.
Réplication : MongoDB prend en charge des Replica Sets, garantissant la haute disponibilité des données et la tolérance aux pannes.
Indexation avancée : Prise en charge d’indexe secondaires pour optimiser les performances des requêtes.

Avantages/inconvénients de MongoDB

Avantages :

Flexibilité des schémas :

Les documents JSON permettent de stocker des données avec des structures dynamiques, évitant le besoin de migrations complexes.

Performance élevée pour les grandes volumiétries :

MongoDB excelle dans les scénarios avec un haut volume de données non structurées ou semi-structurées.

Haute disponibilité et scalabilité :

Avec les Replica Sets et le sharding, MongoDB peut évoluer facilement pour répondre à des besoins croissants.

Facilité d’intégration :

MongoDB offre des connecteurs pour plusieurs langages de programmation (écosystème MongoDB Drivers).

Inconvénients :

Consommation mémoire élevée :

Les documents JSON/BSON sont plus volumineux que les lignes d’une base relationnelle classique, augmentant les besoins en stockage.

Manque de support pour les transactions complexes :

Bien que MongoDB prenne en charge les transactions multi-documents depuis la version 4.0, elles restent moins performantes que dans les bases relationnelles comme MySQL.

Apprentissage :

Les développeurs habitués aux bases relationnelles peuvent rencontrer une courbe d’apprentissage avec MongoDB.

Coûts de mise à l’échelle :

La gestion des clusters MongoDB (scalabilité horizontale) peut être plus coûteuse en infrastructure.

Étude approfondie : Impact de la réplication sur les performances de MongoDB

La réplication est un mécanisme essentiel de MongoDB, permettant de garantir la haute disponibilité et la résilience des données. MongoDB utilise des Replica Sets pour gérer la réplication. Un Replica Set est un groupe de processus MongoDB qui maintiennent les mêmes données via une synchronisation continue. Voici les éléments à considérer :

Fonctionnement de la réplication

Architecture :

Un Replica Set comprend un nœud principal (primary) et plusieurs nœuds secondaires (secondaries).

Le nœud principal gère toutes les opérations d’écriture. Les nœuds secondaires répliquent ces données en lisant les journaux d’opérations (oplogs).

Tolérance aux pannes :

Si le nœud principal devient inaccessible, un nouveau nœud principal est élu parmi les secondaires.

Impact sur les performances

Latence d’écriture :

Les écritures sur le nœud principal sont immédiatement répercutées dans les journaux d’opérations, puis propagées aux nœuds secondaires. 
Cela peut augmenter la latence si plusieurs nœuds doivent être synchronisés avant la confirmation (à cause des paramètres de write concern).

Performances de lecture :

En configurant les applications pour lire depuis les nœuds secondaires (à l’aide des read preferences), il est possible de répartir la charge de lecture, améliorant ainsi les performances globales.

Risque de goulots d’étranglement :

Si le nœud principal est surchargé ou si le réseau entre les nœuds est lent, les opérations d’écriture peuvent subir des ralentissements.

Scénarios de test à évaluer

Écriture avec write concern "majority" :

Mesurer l’impact sur la latence d’écriture en augmentant le nombre de réplicas requis pour confirmer une écriture.

Lecture depuis un nœud secondaire :

Comparer les temps de lecture depuis le nœud principal et depuis les nœuds secondaires.

Election de nouveaux primaires :

Simuler une panne du nœud principal et mesurer le temps nécessaire pour élire un nouveau primaire.

Comparaison avec MySQL

Dans MySQL, la réplication fonctionne selon un modèle maître-esclave classique. Les différences incluent :

Protocole de réplication :

MongoDB utilise les journaux d’opérations (oplogs), tandis que MySQL utilise des logs binaires.

Consistance :

MongoDB offre plus de contrôle avec les paramètres de write concern et read preferences.

Performance :

MySQL peut offrir des temps d’écriture plus rapides en mode asynchrone, mais cela se fait au détriment de la cohérence immédiate des données.

En résumé, la réplication est une fonctionnalité puissante de MongoDB qui impacte directement les performances selon la configuration. Elle est idéale pour les applications critiques qui nécessitent une haute disponibilité et une scalabilité horizontale, mais peut augmenter la latence dans des scénarios intensifs d’écriture.


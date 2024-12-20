python3 generate_data.py &&
docker compose down -v --remove-orphans &&
docker compose up mysql-standalone -d &&
# Attente de la disponibilité du serveur
sleep 10 &&
python3 mysql.py --standalone &&
docker compose down -v --remove-orphans &&
sleep 5 &&
docker compose up mysql-sharded-initiate &&
python3 mysql.py --sharded &&
docker compose down -v --remove-orphans &&
sleep 5 &&
docker compose up mongo-standalone -d &&
# Attente de la disponibilité du serveur
sleep 10 &&
python3 mongodb.py --standalone &&
docker compose down -v --remove-orphans &&
sleep 5 &&
docker compose up mongo-replica-initiate &&
python3 mongodb.py --replica &&
docker compose down -v --remove-orphans &&
sleep 10 &&
docker compose up mongo-sharded-cluster &&
python3 mongodb.py --sharded &&
docker compose down -v --remove-orphans

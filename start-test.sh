python3 generate_data.py &&
docker compose down -v --remove-orphans
docker compose up start_mysql &&
python3 mysql.py &&
docker compose down -v --remove-orphans
docker compose up start_mongo &&
python3 mongodb.py &&
docker compose down -v --remove-orphans
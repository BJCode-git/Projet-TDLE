import mysql.connector
from os import getenv
from dotenv import load_dotenv



def connect():
	load_dotenv()
	connect_params = {	'host': getenv('MYSQL_HOST', 'localhost'),
						'user': getenv('MYSQL_USER', 'root'),
						'password': getenv('MYSQL_PASSWORD', ''),
						'database': getenv('MYSQL_DATABASE', 'database-test')}
 
	return mysql.connector.connect(**connect_params)

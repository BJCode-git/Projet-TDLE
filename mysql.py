
from os import getenv
from dotenv import load_dotenv

import pymysql

from time import perf_counter_ns as time_ns

# For generating data and handling data
from  generate_data import extract_books_from_file, extract_updated_books_from_file, Book
from  generate_data import num_records, num_records_per_many, generated_file, updated_file

# for graphing
import matplotlib.pyplot as plt

# For system information
from platform import system, release, machine, architecture, python_version
from psutil import cpu_count, virtual_memory
from cpuinfo import get_cpu_info

# For logging
from logging import getLogger, basicConfig, INFO, DEBUG, ERROR, FileHandler
from sys import stderr


operation_times		= {}
failed_operations	= {}
system_info			= ""

def add_operation_time(operation, time):
	"""
	Add the time of an operation
	"""
	global operation_times
	if operation not in operation_times:
		operation_times[operation] = [time]
	operation_times[operation].append[time]

class MySQL:

	def __init__(self, using_replica=False, using_shard=False):
		
		self.connection = None
		#self.cursor 	= None
		self.db 		= None
		self.host 		= None
		self.user 		= None
		self.password 	= None
		self.port 		= None
		self.logger		= getLogger(__name__)
		self.logger.setLevel(DEBUG)
		self.logger.addHandler(FileHandler("logs/mysql.log"))
		
		try:
			load_dotenv()
			if using_replica:
				self.host = getenv("MYSQL_REPLICA_HOST", "localhost")
			elif using_shard:
				self.host = getenv("MYSQL_SHARD_HOST", "localhost")
			else:
				self.host 		= getenv("MYSQL_HOST", "localhost")

			self.user 		= getenv("MYSQL_USER", "root")
			self.db 		= getenv("MYSQL_DB", "MYSQL_DATABASE")
			self.password 	= getenv("MYSQL_PASSWORD", "")
			self.port 		= getenv("MYSQL_PORT", 3306)

		except Exception as e:
			self.logger.error("Error loading environment variables: %s", e)
			raise Exception("Error loading environment variables")
		
		try:
			self.connection = pymysql.connect(
				host=self.host,
				user=self.user,
				password=self.password,
				port=self.port,
				autocommit=True
			)
		except Exception as e:
			self.logger.error("Error connecting to MySQL: %s", e)
			raise ValueError("Error connecting to MySQL")

		self.logger.info("MySQL object created")

	def __del__(self):
		self.close()
		self.logger.info("MySQL object deleted")

	def close(self):
		if self.connection:
			self.connection.close()
		self.logger.info("MySQL connection closed")

	def create_one(self, data: Book):
		"""
		Create one record in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s)"
    
				start_time = time_ns()
				rows = cursor.execute(sql, (data.id, data.title, data.author, data.published_date, data.genre, data.price, data.copies_sold, data.ran))
				end_time = time_ns()

				add_operation_time("create_one", end_time-start_time)
				self.logger.debug(f"inserted {rows} record: %s", data.__dict__)
		except Exception as e:
			self.logger.error("Error creating record: %s", e)
   
	def create_many(self, data: list[Book]):
		"""
		Create many records in the database
		"""
		try:
      
			with self.connection.cursor() as cursor:
				sql = f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s)"
				values = [(d.id,d.title, d.author, d.published_date, d.genre, d.price, d.copies_sold, d.ran) for d in data]
    
				start_time = time_ns()
				rows = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("create_many", end_time-start_time)

				self.logger.debug(f"inserted {rows} records: %s", [d.__dict__ for d in data])
    
		except Exception as e:
			self.logger.error("Error creating records: %s", e)

	def update_one(self, original : Book, updated : Book):
		"""
		Update one record in the database
		"""
		try:
	
			with self.connection.cursor() as cursor:
				sql = f"UPDATE {self.db} SET title=%s, author=%s, published_date=%s, genre=%s, price=%s, copies_sold=%s, ran=%s 
						WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"

				start_time = time_ns()
				nb_rows_affected = cursor.execute(sql, 
										(updated.title, updated.author, updated.published_date, updated.genre, updated.price, updated.copies_sold, updated.ran, 
										original.id, original.title, original.author, original.published_date, original.genre, original.price, original.copies_sold, original.ran))
				end_time = time_ns()
				add_operation_time("update_one", end_time-start_time)

				self.logger.debug(f"updated {nb_rows_affected} record: %s", updated.__dict__)

		except Exception as e:
			self.logger.error("Error updating record: %s", e)

	def update_many(self,updated : list[Book]):
		"""
		Update many records in the database
		"""
		try:

			with self.connection.cursor() as cursor:
				sql = f"UPDATE {self.db} 
						SET price = price + 5.95 , 
							copies_sold = copies_sold + 100 
						WHERE ran={updated.ran}"
				values = [(d.price, d.copies_sold, d.ran) for d in updated]

				start_time = time_ns()
				nb_rows_affected = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("update_many", end_time-start_time)
	
				self.logger.debug(f"updated {nb_rows_affected} records: %s", [d.__dict__ for d in updated])

		except Exception as e:
			self.logger.error("Error updating records: %s", e)
   
	def delete_one(self, data: Book):
		"""
		Delete one record in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"DELETE FROM {self.db} WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"
				
				start_time = time_ns()
				rows = cursor.execute(sql, (data.id, data.title, data.author, data.published_date, data.genre, data.price, data.copies_sold, data.ran))
				end_time = time_ns()
				add_operation_time("delete_one", end_time-start_time)
    
				self.logger.debug(f"deleted {rows} record: %s", data.__dict__)
		except Exception as e:
			self.logger.error("Error deleting record: %s", e)

	def delete_many(self, data: list[Book]):
		"""
		Delete many records in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"DELETE FROM {self.db} WHERE ran=%s"
				values = [(d.ran) for d in data]

				start_time = time_ns()
				rows = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("delete_many", end_time-start_time)
	
				self.logger.debug(f"deleted {rows} records: %s", [d.__dict__ for d in data])
		except Exception as e:
			self.logger.error("Error deleting records: %s", e)

	def select_one(self, data: Book):
		"""
		Select one record in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"SELECT * FROM {self.db} WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"
				
				start_time = time_ns()
				rows = cursor.execute(sql, (data.id, data.title, data.author, data.published_date, data.genre, data.price, data.copies_sold, data.ran))
				end_time = time_ns()
				add_operation_time("select_one", end_time-start_time)
	
				self.logger.debug(f"selected {rows} record: %s", data.__dict__)
				return cursor.fetchone()
		except Exception as e:
			self.logger.error("Error selecting record: %s", e)
	
	def select_all(self, data: list[Book]):
		"""
		Select many records in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"SELECT * FROM {self.db} WHERE ran=%s"
				values = [(d.ran) for d in data]

				start_time = time_ns()
				rows = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("select_all", end_time-start_time)

				self.logger.debug(f"selected {rows} records: %s", [d.__dict__ for d in data])
				return cursor.fetchall()
		except Exception as e:
			self.logger.error("Error selecting records: %s", e)
	
	def create_index(self, index_name, columns):
		"""
		Create an index in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"CREATE INDEX {index_name} ON {self.db} ({columns})"
				rows = cursor.execute(sql)
				self.logger.debug(f"created index {index_name} on columns {columns}")
		except Exception as e:
			self.logger.error("Error creating index: %s", e)
	
	def create_indexes(self, indexes):
		"""
		Create many indexes in the database
		"""
		for index in indexes:
			self.create_index(index.name, index.columns)


#### Utilitaires ####

def get_system_info():
	"""
	Display system information
	"""
	global system_info
	if system_info == "":
		system_info = f"Python : {python_version()}\nSystem : {system()} {release()}\nMachine : {machine()} {architecture()[0]}\nCPU : {get_cpu_info()['brand_raw']} - {cpu_count(logical=False)} cores - {cpu_count(logical=True)} threads\nRAM : {int(virtual_memory().total/1024**3)} Go"

def print_failed_operations():
	"""
	Display failed operations
	"""
	global failed_operations
	if failed_operations != {}:
		print("Failed operations :")
		for operation in failed_operations:
			print(f"\t-Operation : {operation}")
			for query,message in failed_operations[operation]:
				print(f"\t\t**Query : {query}")
				print(f"\t\t**Message : {message}")

def plot_operation_times(test_name=""):
	"""
	Plot the times of the operations
	"""
	global operation_times
	# On va créer un graphique pour chaque opération
	for operation in operation_times:
		plt.plot(operation_times[operation], label=operation,scalex=True,scaley=True)
		plt.title('Time of operations')
		plt.xlabel(test_name+ operation )
		plt.ylabel('Time (µs)')
		#plt.annotate(system_info, (0,0), (0, -40), xycoords='axes fraction', textcoords='offset points', va='top')
		plt.legend()
		plt.savefig(f"plots/MySQL_{test_name}_{operation}.png")
		#plt.show()



###### Tests de performance ######
	###### tries < max_triess avec une seule instance ######

def test(mysql: MySQL,plot_name :str):
	global num_records_per_many, generated_file, updated_file
 
	# On récupère les données
	dataset = extract_books_from_file(generated_file)

	### Tests avec données une par une  ###
 
	## Test d'insertion de données
	mysql.logger.debug("Test insert one by one : ")
	for book in dataset:
		mysql.create_one(book.__dict__)

	## Test de mise à jour de données
 
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file)
	# note : update_dataset contains the original and modified data
	
	for update in updated_dataset:
		original = update[0].__dict__
		modified = update[1].__dict__
	
		if original == modified:
			mysql.logger.error(f"Data are the same : \n\t{original} -> \n\t{modified}")
		else:
			#Sinon on identifie le champ modifié
			new_values = {}
			key = ""
			for key in original:
				if original[key] != modified[key]:
					new_values = {key: modified[key]}
					break
			mysql.update_one(update[0].__dict__,{ "$set": new_values})
			
  
	## Test de lecture de données
	## Test de lecture de données sur la collection "Books", en choississant l'id
	mysql.logger.debug("Test read one by one : ")
	for i in range(0,len(dataset)):
		mysql.read_one({"id":i},print_result=False)

	
	## Test de suppression de données
	mysql.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mysql.delete_one(book.__dict__)
	
	# On a normalement supprimé toutes les données !


	### Tests avec plusieurs données à la fois  ###
	# On envoie à chaque fois num_records_per_many données
	
	## Test d'insertion de données
	mysql.logger.debug("Test insert many : ")
	for i in range(0,len(dataset),num_records_per_many):
		data = [book.__dict__ for book in dataset[i:i+num_records_per_many]]
		mysql.create_many(data)
 
	## Test de mise à jour de données
	mysql.logger.debug("Test update many : ")
	for i in range(0,len(updated_dataset),num_records_per_many):
		# On met à jour les données
		# Avec le champ "ran" qui est entre O  
		mysql.update_many({"ran" : i %num_records_per_many},{ "$inc": {"price" : 5.00, "copies_sold": 100} } )

	dataset.clear()
 
	## Test de lecture de données
	mysql.logger.debug("Test read all : ")
	dataset = mysql.read(print_result=False)

	## Test de suppression de données
	mysql.logger.debug("Test delete many : ")
	for i in range(0,num_records_per_many):
		# On supprime les données
		mysql.delete_many({"ran" : i})

	mysql.logger.debug("Data read : ")
	for data in dataset:
		mysql.logger.debug(data)


	# Dessiner les graphiques
	plot_operation_times(plot_name)
	
	# Afficher les opérations qui ont échoué
	print_failed_operations()
 
	# On supprime toutes les données de la collection
	#mysql.drop_all()
 
	# On réinitialise les données des opérations
	mysql.clear_operation_data()

def test_with_index(mysql: MySQL,plot_name :str):
    
	# On définit les index
	indexes = [	IndexModel("id", unique=True), 
				IndexModel("title"), 
				IndexModel("author"), 
				IndexModel("published_date"), 
				IndexModel("genre"), 
				IndexModel("copies_sold"),
				IndexModel("ran")]
	mysql.logger.debug("Creating indexes...")
	mysql.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test(mysql,plot_name)

if __name__ == "__main__":

	get_system_info()
	
	#try:
	# Test avec une seule instance sans index
	mysql = MySQL()
	mysql.logger.info(system_info)
	mysql.logger.info("\n\nTest avec une seule instance sans index\n\n")
	test(mysql, "single_instance")
	
	# Test avec une seule instance avec index
	mysql.logger.info("\n\nTest avec une seule instance avec index\n\n")
	test_with_index(mysql,"single_instance_with_index")

	# On fermes les connexions
	mysql.close()
	#except Exception as e:
	#	print("Test avec instance unique échoué")
	# 	print(f"Error : {e}")

	try:
		mysql = MySQL(using_replica_set=True)
  
		# Test avec réplication et sans index
		mysql.logger.info("\n\nTest avec réplication et sans index \n\n")
		test(mysql, "replication")
	
		# Test avec réplication et avec index
		mysql.logger.info("\n\nTest avec réplication et avec index \n\n")
		test_with_index(mysql, "replication_with_index")
		
		mysql.close()
	except Exception as e:
		print("Test avec réplication échoué")
		print(f"Error : {e}")

	# Test avec sharding
	try:
		mysql = MySQL(using_sharded_cluster=True)

		mysql.logger.info("\n\nTest avec sharding et sans index \n\n")
		test(mysql, "sharding")
	
		# Test avec une seule instance avec index
		mysql.logger.info("\n\nTest avec sharding et avec index \n\n")
		test_with_index(mysql,"sharding_with_index")
	
		# On fermes les connexions
		mysql.close()
	except Exception as e:
		print(f"Error : {e}")
		print("Test avec sharding échoué")


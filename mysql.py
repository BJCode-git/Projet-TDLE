
from os import getenv, makedirs
from dotenv import load_dotenv

import pymysql

from time import perf_counter_ns as time_ns

from numpy import arange

# For generating data and handling data
from generate_data import extract_books_from_file, extract_updated_books_from_file
from generate_data import generate_book,Book , modify_book 
from generate_data import num_records, num_records_per_many, generated_file, updated_file, get_configuration


# for graphing
import matplotlib.pyplot as plt

# For system information
from platform import system, release, machine, architecture, python_version
from psutil import cpu_count, virtual_memory
from cpuinfo import get_cpu_info

# For logging
from logging import getLogger, basicConfig, INFO, DEBUG, ERROR, FileHandler
from sys import stderr

# For animation
from alive_progress import alive_bar
from threading import Thread, Lock, Event


operation_times		= {}
failed_operations	= {}
system_info			= ""
operations_done		= 0
operation_lock		= Lock()
operation_Event		= Event()


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

	def __update_operation_count(self):
		global operations_done, operation_Event, operation_lock
		with operation_lock:
			operations_done += 1
			operation_Event.clear()
			operation_Event.set()

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


######### Utilitaires #########

def print_system_info():
	"""
	Display system information
	"""
	global system_info
	if system_info == "":
		system_info = f"Python : {python_version()}\nSystem : {system()} {release()}\nMachine : {machine()} {architecture()[0]}\nCPU : {get_cpu_info()['brand_raw']} - {cpu_count(logical=False)} cores - {cpu_count(logical=True)} threads\nRAM : {int(virtual_memory().total/1024**3)} Go"
	print(system_info)

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

	failed_operations.clear()

def violin_plot_operation_times(test_name=""):
	"""
	Plot the times of the operations
	"""
	global operation_times
	
	# On crée un dossier pour les graphiques
	makedirs(f"plots/MongoDB", exist_ok=True)
	makedirs(f"plots/MongoDB/{test_name}", exist_ok=True)
 
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in operation_times:

		plt.violinplot(operation_times[operation],
						showmeans=True, showextrema=True, 
						showmedians=True, quantiles=None,
						points=len(operation_times[operation])
						)	
		plt.title("Temps mesuré pour réaliser l\'opération")

		plt.xlabel("Occurence de l'opération : " + operation)
		plt.ylabel('Time (µs)')
		#plt.annotate(system_info, (0,0), (0, -40), xycoords='axes fraction', textcoords='offset points', va='top')
		#plt.legend()
		# On sauvegarde la figure
		plt.savefig(f"plots/MongoDB/{test_name}/{operation}.png")

		# On réinitialise le graphique
		plt.clf()

def plot_operation_times( data = dict, test_name=""):
	"""
		Affiche le temps des opérations selon la quantité de données dans la base de données
	"""
	global operation_times

	# On crée un dossier pour les graphiques
	makedirs(f"plots/MongoDB", exist_ok=True)
	makedirs(f"plots/MongoDB/{test_name}", exist_ok=True)
 
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in data:
		# On récupère les données de temps en y et les données en x (quantité de données)
		x = [data[operation][i][0] for i in range(len(data[operation]))]
		y = [data[operation][i][1] for i in range(len(data[operation]))]
		# On affiche les données en x et en y
		plt.plot(x,y, label=f"{operation} : µs" )
		plt.title("Temps d'opération en fonction de la quantité de données")
		plt.xlabel("Données dans la base de données")
		plt.ylabel('Time (µs)')
		plt.legend()

		# On sauvegarde la figure
		plt.savefig(f"plots/MongoDB/{test_name}/{operation}.png")

		# On réinitialise le graphique
		plt.clf()
	
	if len(data) == 0:
		print("No data to plot")


######### Tests de performance #########

def global_test_one(mysql: MySQL,plot_name :str ,  nb_data:int = num_records):
	global num_records_per_many, generated_file, updated_file
 
	mysql.logger.info("Test global one by one " + plot_name)
 
	if nb_data < 0:
		raise ValueError("nb_data must be > 0 and <= " + str(num_records))

	# On récupère les données
	dataset = extract_books_from_file(generated_file,nb_data)

	if len(dataset) < nb_data:
		mysql.logger.warning(f"Gathered {len(dataset)} records instead of {nb_data}")
 
  
	nb_data = len(dataset)
	
	### Tests avec données une par une  ###
 
	## Test d'insertion de données
	mysql.logger.debug("Test insert one by one : ")
	for book in dataset:
		mysql.create_one(book.__dict__)

	# Libérer la mémoire
	dataset.clear()
 
	## Test de lecture de données sur la collection "Books", en choississant l'id
	mysql.logger.debug("Test read one by one : ")
	for i in range(0,nb_data):
		mysql.read_one({"id":i},print_result=False)

	## Test de mise à jour de données
 
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
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
			

	## Test de suppression de données
	mysql.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mysql.delete_one(book.__dict__)

	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name)
	except Exception as e:
		mysql.logger.error(f"global_test_one : error plotting -> {e}")

	
	# Afficher les opérations qui ont échoué
	#print_failed_operations()
 
	# On supprime toutes les données de la collection
	mysql.drop_all()	
 
	# On réinitialise les données des opérations
	mysql.clear_operation_data()

def global_test_many(mysql: MySQL,plot_name :str, nb_data:int = num_records):
	global updated_file, generated_file, num_records_per_many, num_records

	mysql.logger.info("Test global many" + plot_name)

	### Tests avec plusieurs données à la fois  ###
	
	if nb_data  < 0: 
		raise ValueError("nb_data must be > 0 and <= " + str(num_records_per_many))

	# On récupère les données
	dataset = extract_books_from_file(generated_file,nb_data)

	if len(dataset) < nb_data:
		mysql.logger.warning(f"Gathered {len(dataset)} records instead of {nb_data}")
	
	nb_data = len(dataset)
	
	# On envoie à chaque fois num_records_per_many données
	
	## Test d'insertion de données
	mysql.logger.debug("Test insert many : ")
	for i in range(0,nb_data,num_records_per_many):
		data = [book.__dict__ for book in dataset[i:i+num_records_per_many]]
		mysql.create_many(data)

	# vide dataset pour libérer la mémoire
	dataset.clear()
 
	## Test de mise à jour de données
	
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
 
	mysql.logger.debug("Test update many : ")
	for i in range(0,len(updated_dataset),num_records_per_many):
		# On met à jour les données
		# Avec le champ "ran" qui est entre O  
		mysql.update_many({"ran" : i %num_records_per_many},{ "$inc": {"price" : 5.00, "copies_sold": 100} } )

	dataset.clear()
 
	## Test de lecture de données
	mysql.logger.debug("Test read all : ")
	mysql.read(print_result=False)

	## Test de suppression de données
	mysql.logger.debug("Test delete many : ")
	for i in range(0,num_records_per_many):
		# On supprime les données
		mysql.delete_many({"ran" : i})


	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name)
	except Exception as e:
		mysql.logger.error(f"global_test_many : error plotting -> {e}")
	
	# Afficher les opérations qui ont échoué
	#print_failed_operations()
 
	# On supprime toutes les données de la collection
	mysql.drop_all()
 
	# On réinitialise les données des opérations
	mysql.clear_operation_data()

def test_one_various_data(mysql: MySQL,plot_name :str, steps=arange(1000,num_records,num_records/1000)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
 	"""
	global operation_times, generated_file

	mysql.logger.info("Test one by one with various data "+ plot_name)
 
	tests_data = {}
	for step in steps:
		
		# On supprime toutes les données de la collection s'il y en a
		mysql.drop_all()

		# On va extraire les données, pour opérer sur les mêmes données
		dataset = extract_books_from_file(generated_file,step)
  
		if len(dataset) < step:
			mysql.logger.error(f"Gathered {len(dataset)} records instead of {step}")

		# On va insérer les données
		for book in dataset:
			mysql.create_one(book.__dict__)

		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations, 
		# pour recommencer les mesures
		operation_times.clear()

		# On procède au test de performance
  
		generate_book.id = dataset[-1]["id"] + 1
		book = generate_book(dataset[-1]["id"] + 1)

		# On teste l'insertion
		mysql.create_one(book)

		# On teste la lecture
		mysql.read_one({"id":book["id"]})

		# On teste la mise à jour
		new_book = modify_book(book)
		mysql.update_one({"id":book["id"]}, {"$set": new_book.__dict__})
	
		# On teste la suppression
		mysql.delete_one({"id":book["id"]})

		# On récupère les temps des opérations
		data = operation_times.copy()

		# On ajoute les données dans le tableau
		for operation in data:
			if operation in tests_data:
				tests_data[operation].append((step,data[operation]))
			else:
				tests_data[operation] = [[step,data[operation]]]

	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,plot_name)
	except Exception as e:
		mysql.logger.error(f"test_one_various_data : error plotting -> {e}")
 
	# On supprime toutes les données de la collection
	mysql.drop_all()

def test_many_various_data(mysql: MySQL,plot_name :str, steps=arange(1000,num_records,num_records/1000)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
	"""
	global operation_times, generated_file
 
	mysql.logger.info("Test many with various data " + plot_name)

	tests_data = {}
	for step in steps:
		
		# On supprime toutes les données de la collection s'il y en a
		mysql.drop_all()

		# On va extraire les données, pour opérer sur les mêmes données
		dataset = extract_books_from_file(generated_file,step)
  
		if len(dataset) < step:
			mysql.logger.error(f"Gathered {len(dataset)} records instead of {step}")
			break

		# On va insérer les données
		max_id = 0
		for book in dataset:
			mysql.create_one(book.__dict__)
			if book["id"] > max_id:
				max_id = book["id"]

		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations, 
		# pour recommencer les mesures
		operation_times.clear()

		## On procède au test de performance

		# Génère les données à insérer
		max_id 				= max_id + 1
		generate_book.id 	= max_id

		books = [generate_book(max_id + i) for i in range(0,num_records_per_many)]
		# Modifie le prix à 0 pour la suppression/lecture exacte de num_records_per_many données
		# en effet un prix à 0 est impossible pour un livre, ce seront donc les données à supprimer
		for i in range(0,len(books)):
			books.price = 0.0

		# On teste l'insertion
		mysql.create_many([book.__dict__ for book in books])

		# On teste la lecture
		mysql.read_many({"price":0.0})

		# On teste la mise à jour
		new_book = modify_book(book)
		mysql.update_one({"id":book["id"]}, {"$set": new_book.__dict__})
	
		# On teste la suppression
		mysql.delete_many({"price":0.0})

		# On récupère les temps des opérations
		data = operation_times.copy()

		# On ajoute les données dans le tableau
		for operation in data:
			if operation in tests_data:
				tests_data[operation].append((step,data[operation]))
			else:
				tests_data[operation] = [[step,data[operation]]]
	
	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,plot_name)
	except Exception as e:
		mysql.logger.error(f"test_many_various_data: error plotting -> {e}")
  
	# On supprime toutes les données de la collection	
	mysql.drop_all()

def test_indexed(mysql: MySQL,plot_name :str, test_function,**kwargs):
	# On définit les index
	indexes = [	IndexModel("id", unique=True), 
				IndexModel("title"), 
				IndexModel("author"), 
				IndexModel("published_date"), 
				IndexModel("genre"), 
				IndexModel("copies_sold"),
				IndexModel("ran")]
	mysql.logger.debug("Creating indexes...")
	# On efface les index si existants
	mysql.drop_indexes()
	# On crée les index
	mysql.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test_function(mysql,plot_name,**kwargs)

def run_tests(mysql: MySQL, type_test:str):
	# Without indexed tests
	try:
		if mysql is None:
			raise ValueError("MySQL instance is None")

		# Supprimer les index si existants
		mysql.drop_indexes()
		#try:
		#	global_test_one(mysql, type_test + "_global_one")
		#except Exception as e:
		#	mysql.logger.error(f"Error with global_test_one : {e}")
		#try:
		#	global_test_many(mysql, type_test + "_global_many")
		#except Exception as e:
		#	mysql.logger.error(f"Error with global_test_many : {e}")
		try:
			test_one_various_data(mysql, type_test + "_various_one")
		except Exception as e:
			mysql.logger.error(f"Error with test_one_various_data : {e}")
		try:
			test_many_various_data(mysql, type_test + "_various_many")
		except Exception as e:
			mysql.logger.error(f"Error with test_many_various_data : {e}")
   
   
		# With indexed tests
		try:
			test_indexed(mysql, type_test + "_global_one_indexed", global_test_one)
		except Exception as e:
			mysql.logger.error(f"Error with global_test_one_indexed : {e}")
		try:
			test_indexed(mysql, type_test + "_global_many_indexed", global_test_many)
		except Exception as e:
			mysql.logger.error(f"Error with global_test_many_indexed : {e}")
		try:
			test_indexed(mysql, type_test + "_various_one_indexed", test_one_various_data)
		except Exception as e:
			mysql.logger.error(f"Error with test_one_various_data_indexed : {e}")
		try:
			test_indexed(mysql, type_test + "_various_many_indexed", test_many_various_data)
		except Exception as e:
			mysql.logger.error(f"Error with test_many_various_data_indexed : {e}")
  
	except Exception as e:
		print(f"run_tests : error -> {e}")
		raise e
	

def print_progress(total,text="Running tests..."):
	global operations_done, operation_Event	
 
	with alive_bar(total) as bar:
		bar.text(text)
		print_progress.run = True
		# Attendre operation_Event
		while operations_done < total and print_progress.run:
			operation_Event.wait()
			operation_Event.clear()
			bar()
			bar.text(print_progress.text)

		bar.text(f"Operations done !")
print_progress.run		= True
print_progress.text		="Running tests..."


if __name__ == "__main__":

	# On affiche les informations système
	print_system_info()

	# On charge la configuration
	get_configuration()
 
	# calcul le nombre total d'opérations à effectuer pour une seule instance de run_tests
 
	# opérations pour 2 test_various_one = 2 * len(steps) * ( update_one + read_one + create_one + delete_one) = 8 * len(steps)
	# opérations pour 2 test_various_many = 2 * len(steps) * ( update_many + read_many + create_many + delete_many) = 8 * len(steps)
	# opérations pour 2 test_one = 2 * ( update_one + read_one + create_one + delete_one) * num_records = 16 * num_records
	# opérations pour 2 test_many = 2 * ( update_many + read_many + create_many + delete_many)* num_records/num_records_per_many = 16 * num_records/num_records_per_many
 	# Au total -> 8 * len(steps) + 8 * len(steps) + 16 * num_records + 16 * num_records/num_records_per_many = 
	# 
	

	steps = arange(1000,num_records,num_records/1000)
	total =  int(16 * (len(steps) +  num_records + num_records/num_records_per_many ))
	del steps
	
	progress_T = Thread(target=print_progress, args=((total,)) )
	progress_T.start()
	
	errors = ""
	
	try:
		mysql_standalone = MySQL(debug_level=INFO)
		print_progress.text = "Tests en mode standalone..."
		run_tests(mysql_standalone, "single_instance")
	except Exception as e:
		print(f"Erreur avec le test en standalone: {e}")
		errors += f"Erreur avec le test en standalone: {e}\n"
	finally:
		if mysql_standalone is not None:
			del mysql_standalone
	

	try:
		mysql_replica = MySQL(using_replica_set=True,debug_level=INFO)
		print_progress.text = "Tests en mode Replica..."
		run_tests(mysql_replica, "replica_set")
		del mysql_replica
	except Exception as e:
		print(f"Erreur avec le test avec Replica Set: {e}")
		errors += f"Erreur avec le test avec Replica Set: {e}\n"
	finally:
		if mysql_replica is not None:
			del mysql_replica
  
	try:
		mysql_sharded = MySQL(using_sharded_cluster=True,debug_level=INFO)
		print_progress.text = "Tests en mode Sharded..."
		run_tests(mysql_sharded, "sharding")
		del mysql_sharded
	except Exception as e:
		print(f"Erreur avec le test avec Shards: {e}")
		errors += f"Erreur avec le test avec Shards: {e}\n"
	finally:
		if mysql_sharded is not None:
			del mysql_sharded
  
	# On finit le thread de progressions
	print_progress.run = False
	operation_Event.set()
	progress_T.join(timeout=1)
	
	print("End of tests")
	print(errors)
	


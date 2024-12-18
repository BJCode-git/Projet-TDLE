
from os import getenv, makedirs
from dotenv import load_dotenv
from argparse import ArgumentParser

import pymysql
from time import perf_counter_ns as time_ns

# For statistics
from numpy import arange, median as np_median, mean, percentile
from numpy.random import normal

# For generating data and handling data
from generate_data import extract_books_from_file, extract_updated_books_from_file
from generate_data import generate_book,Book , modify_book 
from generate_data import num_records, num_records_per_many, generated_file, updated_file, get_configuration

# for graphing
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

# For system information
from platform import system, release, machine, architecture, python_version
from psutil import cpu_count, virtual_memory
from cpuinfo import get_cpu_info

# For logging
from logging import getLogger, Formatter, INFO, DEBUG, ERROR, FileHandler
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

	def __init__(self, using_replica=False, using_shard=False,debug_level=INFO):
		
		self.connection = None
		#self.cursor 	= None
		self.db 		= None
		self.host 		= None
		self.user 		= None
		self.password 	= None
		self.port 		= None
		self.logger		= getLogger("MySQL")
		self.logger.setLevel(debug_level)
		try:
			f = Formatter(fmt='[%(levelname)s] %(filename)s:%(lineno)d - %(message)s')
			fh = FileHandler("logs/mysql-tests.log")
			fh.setFormatter(f)
			self.logger.addHandler(fh)
	
			getLogger("pymysql").setLevel(debug_level)
			getLogger("pymysql").addHandler(FileHandler("logs/mysql.log"))

		except Exception as e:
			self.logger.error("Error creating log file", e)
		
		try:
			load_dotenv()
			if using_replica:
				self.host = getenv("MYSQL_REPLICA_HOST", "localhost")
			elif using_shard:
				self.host = getenv("MYSQL_SHARD_HOST", "localhost")
			else:
				self.host = getenv("MYSQL_HOST", "localhost")

			self.user 		= getenv("MYSQL_USER", "root")
			self.db 		= getenv("MYSQL_DB", "MYSQL_DATABASE")
			self.password 	= getenv("MYSQL_PASSWORD", "")
			self.port 		= int(getenv("MYSQL_PORT", 3306))

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

	def __update_operation_count(self):
		global operations_done, operation_Event, operation_lock
		with operation_lock:
			operations_done += 1
			operation_Event.clear()
			operation_Event.set()

	def close(self):
		try:
			if self.connection:
				self.connection.close()
			self.logger.info("MySQL connection closed")
		except Exception as e:
			self.logger.error("Error closing MySQL connection: %s", e)


	def create_one(self, data: dict, silent = False):
		"""
		Create one record in the database
		"""
		try:
			if not silent:
				self.__update_operation_count()

			with self.connection.cursor() as cursor:
				sql = f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s)"
    
				start_time = time_ns()
				rows = cursor.execute(sql, data)
				end_time = time_ns()

				add_operation_time("create_one", end_time-start_time)
				self.logger.debug(f"inserted {rows} record: %s", data)
		except Exception as e:
			self.logger.error("Error creating record: %s", e)

	def create_many(self, data: list[dict],silent = False):
		"""
		Create many records in the database
		"""
		try:
			if not silent:
				self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s)"

				start_time = time_ns()
				rows = cursor.executemany(sql, data)
				end_time = time_ns()
				add_operation_time("create_many", end_time-start_time)
				self.logger.debug(f"inserted {rows} records: %s", data)
    
		except Exception as e:
			self.logger.error("Error creating records: %s", e)

	def update_one(self, original : dict, updated : dict):
		"""
		Update one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"""UPDATE {self.db} SET title=%s, author=%s, published_date=%s, genre=%s, price=%s, copies_sold=%s, ran=%s
					WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"""

				start_time = time_ns()
				nb_rows_affected = cursor.execute(sql, (updated, original))
				end_time = time_ns()
				add_operation_time("update_one", end_time-start_time)

				self.logger.debug(f"updated {nb_rows_affected} record: %s", updated)

		except Exception as e:
			self.logger.error("Error updating record: %s", e)

	def update_many(self,updated : list[dict]):
		"""
		Update many records in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"""	UPDATE {self.db} 
							SET price = price + 5.95 , 
							copies_sold = copies_sold + 100 
							WHERE id=%s"""
				values = [d["id"] for d in updated]

				start_time = time_ns()
				nb_rows_affected = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("update_many", end_time-start_time)
	
				self.logger.debug(f"updated {nb_rows_affected} records: %s", updated)

		except Exception as e:
			self.logger.error("Error updating records: %s", e)

	def delete_one(self, data: dict):
		"""
		Delete one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"DELETE FROM {self.db} WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"
				
				start_time = time_ns()
				rows = cursor.execute(sql, data)
				end_time = time_ns()
				add_operation_time("delete_one", end_time-start_time)
    
				self.logger.debug(f"deleted {rows} record: %s", data)
		except Exception as e:
			self.logger.error("Error deleting record: %s", e)

	def delete_many(self, data: list[dict]):
		"""
		Delete many records in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"DELETE FROM {self.db} WHERE ran=%s"
				values = [(d["ran"]) for d in data]

				start_time = time_ns()
				rows = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("delete_many", end_time-start_time)
	
				self.logger.debug(f"deleted {rows} records: %s", data)
		except Exception as e:
			self.logger.error("Error deleting records: %s", e)

	def read_one(self, data: dict):
		"""
		Select one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"SELECT * FROM {self.db} WHERE id=%s AND title=%s AND author=%s AND published_date=%s AND genre=%s AND price=%s AND copies_sold=%s AND ran=%s"
				
				start_time = time_ns()
				rows = cursor.execute(sql, data)
				end_time = time_ns()
				add_operation_time("read_one", end_time-start_time)
	
				self.logger.debug(f"selected {rows} record: %s", data)
				return cursor.fetchone()
		except Exception as e:
			self.logger.error("Error selecting record: %s", e)
	
	def read_many(self, data: list[dict]):
		"""
		Select many records in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"SELECT * FROM {self.db} WHERE ran=%s"
				values = [(d.ran) for d in data]

				start_time = time_ns()
				rows = cursor.executemany(sql, values)
				end_time = time_ns()
				add_operation_time("read_many", end_time-start_time)

				self.logger.debug(f"selected {rows} records: %s", data)
				return cursor.fetchall()
		except Exception as e:
			self.logger.error("Error selecting records: %s", e)
	
	def read(self, print_result=True):
		"""
		Select all records in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql = f"SELECT * FROM {self.db}"
				start_time = time_ns()
				rows = cursor.execute(sql)
				end_time = time_ns()
				add_operation_time("read", end_time-start_time)
	
				if print_result:
					self.logger.debug(f"selected {rows} records: %s", cursor.fetchall())
		except Exception as e:
			self.logger.error("Error selecting records: %s", e)
	
	def create_index(self, index_name, column):
		"""
		Create an index in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"CREATE INDEX {index_name} ON {self.db} ({column})"
				rows = cursor.execute(sql)
				self.logger.debug(f"created index {index_name} on column {column}")
		except Exception as e:
			self.logger.error("Error creating index: %s", e)
	
	def create_indexes(self, indexes : list[str]):
		"""
		Create many indexes in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				index_names = [f"{index}_index" for index in indexes]
				sql = f"CREATE INDEX {index_names} ON {self.db} ({indexes})"
				rows = cursor.execute(sql)
				self.logger.debug(f"created indexes {index_names} on columns {indexes}")
		except Exception as e:
			self.logger.error("Error creating indexes: %s", e)

	def drop_index(self, index_name):
		"""
		Drop an index in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"DROP INDEX {index_name} ON {self.db}"
				rows = cursor.execute(sql)
				self.logger.debug(f"dropped index {index_name}")
		except Exception as e:
			self.logger.error("Error dropping index: %s", e)

	def drop_indexes(self, indexes : list[str] | None = None):
		"""
		Drop many indexes in the database
		"""

		try:
			with self.connection.cursor() as cursor:
				if indexes is None:
					sql = f"""SET GROUP_CONCAT_MAX_LEN=10000;
								SELECT CONCAT( 'ALTER TABLE `', table_name ,'` DROP INDEX `', index_name ,'`;')
								FROM information_schema.statistics
								WHERE table_schema = '{self.db}' AND table_name = '{self.db}';"""
				else:
					index_names = [f"{index}_index" for index in indexes]
					sql = f"DROP INDEX {index_names} ON {self.db}"

				rows = cursor.execute(sql)
				self.logger.debug(f"dropped indexes {index_names}")
		
		except Exception as e:
			self.logger.error("Error dropping indexes: %s", e)

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

def violin_plot_operation_times(test_type="test",test_name=""):
	"""
	Plot the times of the operations
	"""
	global operation_times
	
	# On crée un dossier pour les graphiques
	makedirs(f"plots/MySQL/{test_type}/{test_name}", exist_ok=True)
 
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in operation_times:

		data = operation_times[operation]

		# Création d'un modèle de graphique
		fig, ax = plt.subplots(figsize=(10, 6))

		# Création du graphe violon
		violin_parts = ax.violinplot(data,  showmeans=True, showmedians=True, showextrema= False, quantiles=[0.25,0.75],points=len(data))

		# Couleurs des quartiles
		quartile_colors = ['#9999FF','#99FF99','#FF9999' ]  # Bleu, Vert, Rouge
		for body, color in zip(violin_parts['bodies'], quartile_colors):
			body.set_facecolor(color)
			body.set_alpha(0.6)

		# Calcul des stats : médiane, moyenne et quartiles
		q1,q3 ,median, mean = 0, 0, 0, 0
		q1		= percentile(data, 25)
		q3		= percentile(data, 75)
		median	= np_median(data)
		mean	= mean(data)
		

		# Ajout du nuage de points 
		x = normal(loc=1, scale=0.05, size=len(data))  # Ajout de jitter pour éviter l'empilement
		y = data
		ax.scatter(x, y, alpha=0.4, color="teal" , s=2, label=f"Nuage de points")


		# Personnalisation des lignes
		violin_parts['cmedians'].set_color('green')  # Ligne médiane
		violin_parts['cmeans'].set_color('purple')  # Ligne moyenne
		violin_parts['cmeans'].set_linestyle('dashed')  # Moyenne en pointillés
		violin_parts['bodies'][0].set_label('Densité')  # Légende pour la densité
		violin_parts['cquantiles'].set_color('blue')  # Changer la couleur des lignes de quantiles
		violin_parts['cquantiles'].set_linestyle('dashed')   # Style de ligne pleine

		# Légende
		legend_elements = [
			Patch(facecolor='#9999FF', alpha=0.7, label='Densité'),
			Line2D([0], [0], color='green'	, label=f'Médiane : {median:.2f}'),
			Line2D([0], [0], color='purple'	, label=f'Moyenne : {mean:.2f}'),
			Line2D([0], [0], color='blue'	, label=f'Quartiles 1 (25%) : {q1:.2f}'),
			Line2D([0], [0], color='blue'	, label=f'Quartiles 3 (75%) : {q3:.2f}'),
			Line2D([0], [0], marker='o'		, color='w', markerfacecolor='teal', markersize=4, label='Nuage de points'),
		]
		ax.legend(handles=legend_elements, loc='upper right', title=f"{test_name} - {operation}")

		# Ajout des labels et du titre
		ax.set_title(f"Temps mesuré pour réaliser l'opération: {operation}")
		ax.set_ylabel("Temps (µs)")
  
		# On sauvegarde la figure
		plt.savefig(f"plots/MySQL/{test_type}/{test_name}/{operation}.png")

		# On réinitialise le graphique
		plt.clf()

def plot_operation_times( data = dict,test_type="test",test_name=""):
	"""
		Affiche le temps des opérations selon la quantité de données dans la base de données
	"""

	# On crée un dossier pour les graphiques
	makedirs(f"plots/MySQL/{test_type}/{test_name}", exist_ok=True)
	
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in data:
		
		# On récupère les données de temps en y et les données en x (quantité de données)
		# data[operation] = [(nb_donnees,[liste des temps])]
		nb_donnees	= [data[operation][i][0] for i in range(len(data[operation]))]
		moyens		= [mean(data[operation][i][1]) for i in range(len(data[operation]))]
		# On affiche le temps moyen en µs en fonction de la quantité de données
		plt.plot(nb_donnees,moyens, label=f"{operation} : µs" )
		plt.title("Temps moyen d'opération en fonction de la quantité de données")
		plt.xlabel("Données dans la base de données")
		plt.ylabel('Time (µs)')
		plt.legend()

		# On sauvegarde la figure
		plt.savefig(f"plots/MySQL/{test_type}/{test_name}/{operation}.png")

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
		mysql.create_one(book)

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
		original = update[0]
		modified = update[1]
	
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
			mysql.update_one(update[0],{ "$set": new_values})
			

	## Test de suppression de données
	mysql.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mysql.delete_one(book)

	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name, "global_one")
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
		data = [book for book in dataset[i:i+num_records_per_many]]
		mysql.create_many(data)

	# vide dataset pour libérer la mémoire
	dataset.clear()
 
	## Test de mise à jour de données
	
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
 
	mysql.logger.debug("Test update many : ")
	for i in range(0,num_records_per_many):
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
		violin_plot_operation_times(plot_name,"global_test_many")
	except Exception as e:
		mysql.logger.error(f"global_test_many : error plotting -> {e}")
	
	# Afficher les opérations qui ont échoué
	#print_failed_operations()
 
	# On supprime toutes les données de la collection
	mysql.drop_all()
 
	# On réinitialise les données des opérations
	mysql.clear_operation_data()

def test_one_various_data(mysql: MySQL,plot_name :str, steps=arange(1000,num_records,num_records/100)):
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
		mysql.create_many(dataset,silent=True)
		

		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations, 
		# pour recommencer les mesures
		operation_times.clear()

		# On procède au test de performance

		max_id = step + 1
		generate_book.id = max_id
		book = generate_book(max_id)

		# On teste l'insertion
		mysql.create_one(book)

		# On teste la lecture
		mysql.read_one({"id":book["id"]})

		# On teste la mise à jour
		new_book = modify_book(book)
		mysql.update_one({"id":book["id"]}, {"$set": new_book})
	
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

def test_many_various_data(mysql: MySQL,plot_name :str, steps=arange(1000,num_records,num_records/100)):
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
		mysql.create_many(dataset,silent=True)
		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations,  pour recommencer les mesures
		operation_times.clear()

		## On procède au test de performance

		# Génère les données à insérer
		max_id = step + 1
		books = [generate_book(max_id + i) for i in range(0,num_records_per_many)]

		# Modifie le prix à 0 pour la suppression/lecture exacte de num_records_per_many données
		# en effet un prix à 0 est impossible pour un livre, ce seront donc les données à supprimer
		for book in books:
			book["price"]= 0.0

		# On teste l'insertion
		mysql.create_many(books)

		# On teste la lecture
		mysql.read_many({"price":0.0})

		# On teste la mise à jour
		mysql.update_many({"price":0.00}, {"$set": {"genre": "updated"} })
	
		# On teste la suppression
		mysql.delete_many({"price":0.0})

		# On récupère les temps des opérations
		# et on ajoute les données dans le tableau
		for operation in operation_times:
			if operation in tests_data:
				tests_data[operation].append((step,operation_times[operation]))
			else:
				tests_data[operation] = [[step,operation_times[operation]]]
	
	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,plot_name)
	except Exception as e:
		mysql.logger.error(f"test_many_various_data: error plotting -> {e}")
  
	# On supprime toutes les données de la collection	
	mysql.drop_all()

def test_indexed(mysql: MySQL,plot_name :str, test_function,**kwargs):
	# On définit les index
	indexes = [	"id", 
				"title",
				"author", 
				"published_date",
				"genre",
				"copies_sold",
				"ran"]
	mysql.logger.debug("Creating indexes...")
	# On efface les index si existants
	mysql.drop_indexes()
	# On crée les index
	mysql.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test_function(mysql,plot_name,**kwargs)

def run_tests(mysql: MySQL, type_test:str, steps=arange(1000,num_records,num_records/10000)):
	
	if mysql is None:
		raise ValueError("MongoDB instance is None")

	# Supprimer les index si existants
	mysql.drop_indexes()

	# Without indexes tests
	try:
		print_progress.text = "Running "+type_test + "_global_one..."
		global_test_one(mysql, type_test)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_one : {e}")

	try:
		print_progress.text = "Running"+type_test + "_global_many..."
		global_test_many(mysql, type_test)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_many : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_one..."
		test_one_various_data(mysql, type_test,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_one_various_data : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_many..."
		test_many_various_data(mysql, type_test,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_many_various_data : {e}")

	# With indexes tests
	try:
		print_progress.text = "Running "+type_test + "_global_one_indexed..."
		test_indexed(mysql, type_test, global_test_one)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_one_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_global_many_indexed..."
		test_indexed(mysql, type_test + "_indexed", global_test_many)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_many_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_one_indexed..."
		test_indexed(mysql, type_test + "_indexed", test_one_various_data,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_one_various_data_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_many_indexed..."
		test_indexed(mysql, type_test + "_indexed", test_many_various_data,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_many_various_data_indexed : {e}")


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
 
	parser = ArgumentParser(description="MongoDB performance tests")
	parser.add_argument("--verbose",	help="increase output verbosity",	action="store_true")
	# Ajouter des arguments pour savoir quel(s) test(s) effectuer 
	parser.add_argument("--standalone", help="Run tests with a standalone",	action="store_true" )
	parser.add_argument("--replica", 	help="Run tests with replica set",	action="store_true" )
	parser.add_argument("--sharded", 	help="Run tests with shards ",		action="store_true" )
	parser.add_argument("--all", 		help="Run all tests", 				action="store_true" )
 
	args = parser.parse_args()

	if (not args.standalone) and (not args.replica) and (not args.sharded) and (not args.all):
		#parser.error("No action requested, add --standalone, --replica, --sharded or --all")
		args.all = True

	steps	= arange(1000,num_records,num_records/100)
	size 	= len(steps)
 
	# Calcul le nombre total d'opérations à effectuer pour l'affichage de la progression pour une instance de test
	# 2* à chaque fois car test avec et sans index, 4 fois car 4 tests
	total_test_various_one 	= 2 * 4 * size
	total_test_various_many = 2 * 4 * size
	total_test_one			= 2 * 4 * num_records
	#	num_records/num_records_per_many insertion de num_records_per_many données
	#	num_records_per_many CRUD operations
	total_test_many 		= 2 * ( num_records/num_records_per_many + 3 * num_records_per_many)
	total 					= int(total_test_various_one + total_test_various_many + total_test_one + total_test_many )
	coeff = 0
 
	if args.standalone or args.all:
		coeff += 1
	if args.replica or args.all:
		coeff += 1
	if args.sharded or args.all:
		coeff += 1
	# On multiplie par le nombre de tests
	total *= coeff
	
	print("Running tests ...")
	progress_T = Thread(target=print_progress, args=((total,)) )
	progress_T.start()
	
	errors = ""
	debug_level = DEBUG if args.verbose else INFO
	mongo_standalone	= None
	mongo_replica		= None
	mongo_sharded		= None

	if args.standalone or args.all:
		try:
		
			mysql_standalone = MySQL(debug_level=INFO)
			print_progress.text = "Tests en mode standalone..."
			run_tests(mysql_standalone, "single_instance")
	
		except Exception as e:
		
			print(f"Erreur avec le test en standalone: {e}")
			errors += f"Test en standalone: erreur -> {e}\n"
	
		finally:
			if mysql_standalone is not None:
				del mysql_standalone
	
	if args.replica or args.all:
		print("No replica set tests")
		#try:
		#
		#	mysql_replica = MySQL(using_replica_set=True,debug_level=INFO)
		#	print_progress.text = "Tests en mode Replica..."
		#	run_tests(mysql_replica, "replica_set")
		#	del mysql_replica
	#
		#except Exception as e:
		#
		#	print(f"Erreur avec le test avec Replica Set: {e}")
		#	errors += f"Erreur avec le test avec Replica Set: {e}\n"
		#finally:
		#
		#	if mysql_replica is not None:
		#		del mysql_replica

	if args.sharded or args.all:
		try:

			mysql_sharded = MySQL(using_shard=True,debug_level=INFO)
			print_progress.text = "Tests en mode Sharded..."
			run_tests(mysql_sharded, "sharding")

		except Exception as e:
		
			print(f"Erreur avec le test avec Shards: {e}")
			errors += f"Test avec Shards: erreur -> {e}\n"
	
		finally:
		
			if mysql_sharded is not None:
				del mysql_sharded

	# On finit le thread de progressions
	print_progress.run = False
	operation_Event.set()
	progress_T.join(timeout=1)
	
	print("End of tests")
	print(errors)

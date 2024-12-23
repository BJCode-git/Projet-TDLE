
from os import getenv, makedirs, path, remove
from dotenv import load_dotenv
from argparse import ArgumentParser

# For handling signals
from signal import signal, SIGINT, SIGTERM

import pymysql
from time import perf_counter_ns as time_ns
from collections import defaultdict

# For statistics
from numpy import arange, median as np_median, mean as np_mean, std as np_std ,percentile
from numpy.random import normal

# For generating data and handling data
from generate_data import extract_books_from_file, extract_updated_books_from_file ,generated_file, updated_file
from generate_data import generate_book, modify_book #, Book 
from generate_data import num_records, num_records_per_many, nb_measurements
from generate_data import  get_configuration

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


operation_times		= defaultdict(list)
system_info			= ""
operations_done		= 0
operation_lock		= Lock()
operation_Event		= Event()


def add_operation_time(operation, time):
	"""
	Add the time of an operation
	"""
	global operation_times
	# Convert nanoseconds time to microseconds
	time = time/1000
	operation_times[operation].append(time)

class MySQL:

	def __init__(self, using_replica=False, using_shard=False,debug_level=INFO,dbg_file_mode="w"):
		
		self.connection = None
		self.db 		= None
		self.host 		= None
		self.user 		= None
		self.password 	= None
		self.port 		= None
		self.logger		= getLogger("MySQL")
		self.logger.setLevel(debug_level)
		try:
			f 	= Formatter(fmt='[%(levelname)s] %(filename)s:%(lineno)d - %(message)s')
			fh 	= FileHandler("logs/mysql-tests.log",mode=dbg_file_mode)
			fh.setFormatter(f)
			self.logger.addHandler(fh)

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
			self.db 		= getenv("MYSQL_DATABASE", "test")
			self.password 	= getenv("MYSQL_PASSWORD", "")
			self.port 		= int(getenv("MYSQL_PORT", 3306))

		except Exception as e:
			self.logger.error("Error loading environment variables: %s", e)
			raise Exception("Error loading environment variables")
		
		try:
			self.connection = pymysql.connect(
				host=self.host,
				user=self.user,
				database=self.db,
				password=self.password,
				port=self.port,
				autocommit=True,
			)

			# Création de la table si elle n'existe pas
			with self.connection.cursor() as cursor:
				cursor.execute(f"""CREATE TABLE IF NOT EXISTS {self.db} (
					id 				INT 			NOT NULL,
					title 			VARCHAR(255) 	NOT NULL,
					author 			VARCHAR(255) 	NOT NULL,
					published_date 	DATE 			NOT NULL,
					genre 			VARCHAR(255) 	NOT NULL,
					price 			FLOAT 			NOT NULL,
					copies_sold 	INT 			NOT NULL,
					ran 			INT 			NOT NULL
				)""")
				#rows = cursor.execute(f"DESCRIBE {self.db}")
				#self.logger.info(f"Table description : {rows} columns")
				#for row in cursor.fetchall():
				#	self.logger.info(f"\t {row}")
	

		except Exception as e:
			self.logger.error("Error connecting to MySQL: %s", e)
			raise ValueError("Error connecting to MySQL")

		#Utilisé pour stocker les index
		self.__indexes = []

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

			if not isinstance(data, dict):
				self.logger.error(f"Data is not a dict: {type(data)} - {data}")

			with self.connection.cursor() as cursor:
				sql = 	f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) "\
						f"VALUES (%(id)s, %(title)s, %(author)s, %(published_date)s, %(genre)s, %(price)s, %(copies_sold)s, %(ran)s)"

				start_time	= time_ns()
				rows		= cursor.execute(sql, data)
				end_time 	= time_ns()
				add_operation_time("insert", end_time-start_time)

				self.logger.debug(f"inserted {rows} record: ", data)
    
		except Exception as e:
			self.logger.error("Error creating one record: %s", e)
			self.logger.error(f"\t sql : {sql}")
			self.logger.error(f"\t data : {data}")

	def create_many(self, data: list[dict],silent = False):
		"""
		Create many records in the database
		"""
		try:
			if not silent:
				self.__update_operation_count()
			with self.connection.cursor() as cursor:
				sql =	f"INSERT INTO {self.db} (id,title, author, published_date, genre, price, copies_sold,ran) "\
						f"VALUES (%(id)s, %(title)s, %(author)s, %(published_date)s, %(genre)s, %(price)s, %(copies_sold)s, %(ran)s)"
				start_time = time_ns()
				rows = cursor.executemany(sql, data)
				end_time = time_ns()
				add_operation_time("insert", end_time-start_time)
				self.logger.debug(f"inserted {rows} records: %s", data)
    
		except Exception as e:
			self.logger.error("Error creating many records: %s", e)

	def update_one(self, original : dict, updated : dict):
		"""
		Update one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:

				conditions = ""
				for key in original:
					conditions += f'{key}="{original[key]}" AND '
				conditions = conditions[:-4]

				new_values = ""
				for key in updated:
					new_values += f'{key}="{updated[key]}", '
				new_values = new_values[:-2]

				sql = 	f"UPDATE {self.db} "\
						f"SET {new_values} "\
						f"WHERE {conditions} LIMIT 1"
       
				start_time = time_ns()
				nb_rows_affected = cursor.execute(sql)
				end_time = time_ns()
				add_operation_time("update", end_time-start_time)

				self.logger.debug(f"updated {nb_rows_affected} record: %s", updated)

		except Exception as e:
			self.logger.error("Error updating one record: %s", e)

	def update_many(self,original:dict,updated : list[dict] | dict):
		"""
		Update many records in the database
		"""
		try:
			self.__update_operation_count()

			if not isinstance(updated, list):
				updated = [updated]

			with self.connection.cursor() as cursor:

				conditions = ""
				for key in original:
					conditions += f'{key}="{original[key]}" AND '
				conditions = conditions[:-4]

				new_values = ""
				for key in updated[0]:
					new_values += f'{key}=%({key})s, '
				new_values = new_values[:-2]

				sql = 	f"UPDATE {self.db} "\
						f"SET {new_values} "\
						f"WHERE {conditions}"

				start_time	= time_ns()
				nb_rows_affected = cursor.executemany(sql, updated)
				end_time	= time_ns()
				add_operation_time("update", end_time-start_time)
	
				self.logger.debug(f"updated {nb_rows_affected} records: ", updated)

		except Exception as e:
			self.logger.error("Error updating many records: %s", e)

	def delete_one(self, data: dict):
		"""
		Delete one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				conditions=""
				for key in data:
					conditions += f'{key}="{data[key]}" AND '
				conditions = conditions[:-4]
    
				sql = 	f"DELETE FROM {self.db} "\
						f"WHERE {conditions} "\
						f"LIMIT 1"
				
				start_time = time_ns()
				rows = cursor.execute(sql)
				end_time = time_ns()
				add_operation_time("delete", end_time-start_time)

				self.logger.debug(f"deleted {rows} record: ", data)
		except Exception as e:
			self.logger.error("Error deleting one record: %s", e)
			self.logger.error(f"\t sql : {sql}")

	def delete_many(self, data: list[dict] | dict):
		"""
		Delete many records in the database
		"""
		try:
			self.__update_operation_count()
			if not isinstance(data, list):
				data = [data]
			with self.connection.cursor() as cursor:
				conditions = ""
				for key in data[0]:
					conditions += f'{key}=%({key})s AND '
				conditions = conditions[:-4]

				sql = f"DELETE FROM {self.db} WHERE {conditions}"

				start_time = time_ns()
				rows = cursor.executemany(sql, data)
				end_time = time_ns()
				add_operation_time("delete", end_time-start_time)
	
				self.logger.debug(f"deleted {rows} records: %s", data)
		except Exception as e:
			self.logger.error("Error deleting many records: %s", e)
			self.logger.error(f"\t sql : {sql}")

	def read_one(self, data: dict, print_result: bool =False):
		"""
		Select one record in the database
		"""
		try:
			self.__update_operation_count()
			with self.connection.cursor() as cursor:
				conditions = ""
				for key in data:
					conditions += f'{key}="{key}" AND '
				conditions = conditions[:-4]

				sql = 	f"SELECT * FROM {self.db} "\
						f"WHERE {conditions}"
		
				start_time = time_ns()
				rows = cursor.execute(sql)
				end_time = time_ns()
				add_operation_time("find", end_time-start_time)
				result = cursor.fetchone()
				if print_result:
					self.logger.debug(f"selected {rows} record: ", data)
					self.logger.info(f"result: {result}")
					
				return result

		except Exception as e:
			self.logger.error("Error selecting one record: %s", e)
			self.logger.error(f"\t sql : {sql}")
			self.logger.error(f"\t data : {data}")
	
	def read_many(self, data: list[dict] | dict, print_result : bool =False):
		"""
		Select many records in the database
		"""
		try:
			self.__update_operation_count()
			if not isinstance(data, list):
				data = [data]
			with self.connection.cursor() as cursor:
				# On récupère les clés des données
				keys = ""
				values = ""
				for key in data[0]:
					keys += f'{key},'
					values += f'%({key})s,'
				#on enlève la dernière virgule
				keys = keys[:-1]
				values = values[:-1]

				sql =	f"SELECT * FROM {self.db} "\
						f"WHERE ({keys}) = ({values})"

				#values = [(d.ran) for d in data]

				start_time = time_ns()
				rows = cursor.executemany(sql,data)
				end_time = time_ns()
				add_operation_time("find", end_time-start_time)
			
				result = cursor.fetchall()
				if print_result:
					self.logger.debug(f"selected {rows} records: %s", data)
					self.logger.info(f"result: {result}")
					
				return cursor.fetchall()
		except Exception as e:
			self.logger.error("Error selecting many records: %s", e)
			self.logger.error(f"\t sql : {sql}")
	
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
				add_operation_time("find", end_time-start_time)
	
				if print_result:
					self.logger.debug(f"selected {rows} records: %s", cursor.fetchall())

		except Exception as e:
			self.logger.error("Error selecting records: %s", e)
	
	def create_index(self, index):
		"""
		Create an index in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"CREATE INDEX `{index}_index` ON `{self.db}` (`{index}`)"
				cursor.execute(sql)
				self.__indexes.append(f"{index}")

				self.logger.debug(f"created index {index}_index  on column {index}")
		except pymysql.Error as e:
			# On check si c'est une erreur de duplication
			if e.args[0] == 1061:
				# si c'est le cas, on avertit simplement
				self.logger.warning(f"Index '{index}_index' already exists")
			else:
				self.logger.error(f"Pymysql Error creating index '{index}_index' -> {e}")
		except Exception as e:
			self.logger.error(f"Error creating index '{index}_index' -> {e}")
	
	def create_indexes(self, indexes : list[str]):
		"""
		Create many indexes in the database
		"""
		try:

			for index in indexes:
				self.create_index(index)

			#self.logger.debug(f"created indexes {indexes}")

		except pymysql.Error as e:
			# On check si c'est une erreur de duplication
			if e.args[0] == 1061:
				# si c'est le cas, on ignore l'erreur
				self.warning(f"Index '{index}_index' already exists")
			else:
				self.logger.error(f"Pymysql Error creating index '{index}_index' -> {e}")

		except Exception as e:
			self.logger.error(f"Error creating indexes: {indexes} -> {e}")

	def drop_index(self, index_name:str):
		"""
		Drop an index in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				# On vérifie si l'index est bien nommé
				if not index_name.endswith("_index"):
							index_name += "_index"
				sql = f"DROP INDEX `{index_name}` ON `{self.db}`"
				cursor.execute(sql)

				try:
					self.__indexes.remove(index_name)
				except ValueError:
					pass
 
				self.logger.debug(f"dropped index {index_name}")

		except pymysql.Error as e:
			# On regarde si c'est une erreur d'existance de l'index 
			if e.args[0] == 1091:
				self.logger.warning(f"L'inex '{index_name}' n'existe pas")
			else:
				self.logger.error(f"Pymysql Error dropping index '{index_name}' -> {e}")
			
		except Exception as e:
			self.logger.error("Error dropping index: %s", e)

	def drop_indexes(self,index_names : list[str] | None = None):
		"""
		Drop all indexes in the database if no index_names are provided
		Else drop the indexes in the list
		"""

		sql		= ""
		try:
			with self.connection.cursor() as cursor:

				# Si aucun index n'est fourni, on récupère tous les index et on les supprime
				if index_names is None or index_names == []:
					cursor.execute(f"SHOW INDEXES FROM {self.db}")
					index_names = [index[2] for index in cursor.fetchall()]

				for index in index_names:
					self.drop_index(index)

				#self.logger.debug(f"dropped indexes {index_names}")

		except pymysql.Error as e:
			self.logger.error(f"Pymysql Error dropping indexes '{index_names}' -> {e}")
			self.logger.error(f"\t sql : {sql}")
		
		except Exception as e:
			self.logger.error("Error dropping indexes: %s", e)

	def drop_all(self):
		"""
		Drop all records in the database
		"""
		try:
			with self.connection.cursor() as cursor:
				sql = f"DELETE FROM {self.db}"
				cursor.execute(sql)
				self.logger.debug(f"deleted all records")
		except Exception as e:
			self.logger.error("Error deleting all records: %s", e)

######### Utilitaires #########

def print_system_info():
	"""
	Display system information
	"""
	global system_info
	if system_info == "":
		system_info = f"Python : {python_version()}\nSystem : {system()} {release()}\nMachine : {machine()} {architecture()[0]}\nCPU : {get_cpu_info()['brand_raw']} - {cpu_count(logical=False)} cores - {cpu_count(logical=True)} threads\nRAM : {int(virtual_memory().total/1024**3)} Go"
	print(system_info)

def violin_plot_operation_times(test_type="test",test_name=""):
	"""
	Plot the times of the operations
	"""
	global operation_times
	
	if len(operation_times) == 0:
		print(f" {test_type} : {test_name} -> No data to plot")
		return
 
	# Réveille le thread de progression
	with operation_lock:
		operation_Event.set()
	
	change_progression_text(f"Generating plots for {test_type}/{test_name} ...")
	
	# On crée un dossier pour les graphiques
	makedirs(f"plots/MySQL/{test_type}", exist_ok=True)
 
	# On va créer un graphique regroupant les 4 opérations : insertion, lecture, mise à jour et suppression
	fig, axes = plt.subplots(2,2,figsize=(12, 8))
	axes = axes.flatten()
	idx = 0
	for operation in operation_times:
		ax = axes[idx]
		data = operation_times[operation]

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
		mean	= np_mean(data)
		std 	= np_std(data)
		
		# Ajout du nuage de points 
		x = normal(loc=1, scale=0.05, size=len(data))  # Ajout de jitter pour éviter l'empilement
		y = data
		ax.scatter(x, y, alpha=0.4, color="teal" , s=2, label=f"Nuage de points")

		# Personnalisation des lignes
		violin_parts['cmedians'].set_color('green')  # Ligne médiane
		violin_parts['cmeans'].set_color('red')  # Ligne moyenne
		violin_parts['cmeans'].set_linestyle('dashed')  # Moyenne en pointillés
		violin_parts['bodies'][0].set_label('Densité')  # Légende pour la densité
		violin_parts['cquantiles'].set_color('blue')  # Changer la couleur des lignes de quantiles
		violin_parts['cquantiles'].set_linestyle('dashed')   # Style de ligne pleine

		# Légende
		legend_elements = [
			Patch(facecolor='#9999FF', alpha=0.7, label='Densité'),
			Line2D([0], [0], color='green'	, label=f'Médiane : {median:.2f} (µs)'),
			Line2D([0], [0], color='red'	, label=f'Moyenne : {mean:.2f} +/- {std:.2f} écart (µs)'),
			Line2D([0], [0], color='blue'	, label=f'Quartiles (25%) : {q1:.2f}'),
			Line2D([0], [0], color='blue'	, label=f'Quartiles (75%) : {q3:.2f}'),
			Line2D([0], [0], marker='o'		, color='w', markerfacecolor='teal', markersize=4, label='Nuage de points'),
		]
		ax.legend(handles=legend_elements, loc='best')

		# Ajout des labels et du titre
		ax.set_title(f"Distribution du temps de réalisation pour {len(data)} opération: {operation}")
		ax.set_ylabel("Temps (µs)")

		idx += 1
  
	# Ajuster l'espace entre les sous-graphes
	plt.tight_layout()

	# On sauvegarde la figure, au cas où elle existe déjà, on la supprime
	save_path = f"plots/MySQL/{test_type}/{test_name}.png"
	if path.exists(save_path):
		remove(save_path)
	plt.savefig(save_path)

	# on ferme la figure
	plt.close()	

def plot_operation_times( data:dict,step,test_type="test",test_name=""):
	"""
		Affiche le temps des opérations selon la quantité de données dans la base de données
	"""

	if len(data) == 0:
		print(f" {test_type} : {test_name} -> No data to plot")
		return

	# On crée un dossier pour les graphiques
	makedirs(f"plots/MySQL/{test_type}/", exist_ok=True)
	
	# On va créer un graphique qui contient les 4 opérations : insertion, lecture, mise à jour et suppression en même temps
	fig, axes	= plt.subplots(2, 2, figsize=(12, 8))
	axes		= axes.flatten() 
	idx			= 0
	for operation in data:
		ax = axes[idx]
  
		# Calcul des stats : médiane, moyenne et quartiles		
		moyenne	= np_mean	(data[operation])
		mediane	= np_median	(data[operation])
		std 	= np_std	(data[operation])
		q1		= percentile(data[operation], 25)
		q3		= percentile(data[operation], 75)

		# On affiche le temps moyen en µs en fonction de la quantité de données
		ax.plot(steps,data[operation], label=f"{operation} : µs" )
	
		# On trace les lignes de moyenne, médiane et quartiles
		ax.axhline(y=moyenne,	color='r', linestyle='--')
		ax.axhline(y=mediane,	color='g', linestyle='--')
		ax.axhline(y=q1,		color='b', linestyle='--')
		ax.axhline(y=q3,		color='b', linestyle='--')
  
		# on ajoute dans la légende les couleurs des lignes et les labels
		legend_elements = [
			Line2D([0], [0], color='r', linestyle='--', label=f'Moyenne : {moyenne:.2f} +/- {std:.2f} écart (µs)'),
			Line2D([0], [0], color='g', linestyle='--', label=f'Médiane : {mediane:.2f} (µs)'),
			Line2D([0], [0], color='b', linestyle='--', label=f'Quartiles 1 (25%) : {q1:.2f} (µs)'),
			Line2D([0], [0], color='b', linestyle='--', label=f'Quartiles 3 (75%) : {q3:.2f} (µs)'),
		]
		
		# Personnalisation du graphique
		ax.set_title(f"{operation} : Temps d'execution par quantité de données initiales")
		ax.set_xlabel("Données dans la base de données")
		ax.set_ylabel('Time (µs)')
		ax.legend(handles=legend_elements, loc='best' )
  
		idx += 1
  
	# Ajuster l'espace entre les sous-graphes
	plt.tight_layout()

	# On sauvegarde la figure, au cas où elle existe déjà, on la supprime
	save_path = f"plots/MySQL/{test_type}/{test_name}.png"
	if path.exists(save_path):
		remove(save_path)
	plt.savefig(save_path)

	# On réinitialise le graphique
	#plt.clf()
	# on ferme la figure
	plt.close()


######### Tests de performance #########

def global_test_one(mysql: MySQL,plot_name :str ,  nb_data:int = num_records):
	global num_records,num_records_per_many, generated_file, updated_file, operation_times
 
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
			mysql.update_one(update[0], modified)
			

	## Test de suppression de données
	mysql.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mysql.delete_one(book)

	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name, "global_test_one")
	except Exception as e:
		mysql.logger.error(f"global_test_one : error plotting -> {e}")

	
	# On supprime toutes les données de la collection
	mysql.drop_all()	
 
	# On réinitialise les données des opérations
	operation_times.clear()

def global_test_many(mysql: MySQL,plot_name :str, nb_data:int = num_records):
	global updated_file, generated_file, num_records_per_many, num_records, operation_times

	mysql.logger.info("Test global many " + plot_name)

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
	#updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
 
	mysql.logger.debug("Test update many : ")
	for i in range(0,num_records_per_many):
		# On met à jour les données
		# Avec le champ "ran" qui est entre O  
		mysql.update_many({"ran" : i %num_records_per_many}, {"price" : 5.00, "copies_sold": 100} )

	dataset.clear()
 
	## Test de lecture de données
	mysql.logger.debug("Test read all : ")
	# On lit les données où le champ "ran" est entre 0 et num_records_per_many
	for i in range(0,num_records_per_many):
		mysql.read_many({"ran" : i},print_result=False)

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
	

	# On supprime toutes les données de la collection
	mysql.drop_all()
 
	# On réinitialise les données des opérations
	operation_times.clear()

def test_one_various_data(mysql: MySQL,plot_name :str, steps=arange(1000,num_records,num_records/100)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
 	"""
	global operation_times, generated_file

	mysql.logger.info("Test one by one with various data "+ plot_name)
 
	# On supprime les données de la collection s'il y en a
	mysql.drop_all()
 
	# On extrait toutes les données dont on aura besoin
	dataset = extract_books_from_file(generated_file,steps[-1])
	if len(dataset) < steps[-1]:
		mysql.logger.warning(f"Gathered {len(dataset)} records instead of {step}")
	
	tests_data = defaultdict(list)
	try:
		a=0
		for step in steps:
			step = int(step)

			# On arrête si on dépasse le nombre de données disponibles
			if step > len(dataset):
				mysql.logger.warning(f"Step {step} > {len(dataset)}")
				break

			# On va insérer les données  manquantes pour avoir step données initiales dans la base
			try:
				if a < step:
					mysql.create_many(dataset[a:step],silent=True)
			except Exception as e:
				mysql.logger.error(f"test_one_various_data : init error {e}")
			finally:
				a = step
		
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
			mysql.update_one({"id":book["id"]}, new_book)
		
			# On teste la suppression
			mysql.delete_one({"id":book["id"]})

			# On ajoute les données dans le tableau

			for operation in operation_times:
				tests_data[operation].extend(operation_times[operation])

	except Exception as e: 
		mysql.logger.error(f"test_one_various_data: error -> {e}")

	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,steps,plot_name,"test_one_various_data")
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

	# On supprime les données de la collection s'il y en a
	mysql.drop_all()
 
	# On extrait toutes les données dont on aura besoin
	dataset = extract_books_from_file(generated_file,steps[-1])
	if len(dataset) < steps[-1]:
		mysql.logger.warning(f"Gathered {len(dataset)} records instead of {step}")
	
	tests_data = defaultdict(list)
	try:
		a=0
		for step in steps:
			step = int(step)

			# On arrête si on dépasse le nombre de données disponibles
			if step > len(dataset):
				mysql.logger.warning(f"Step {step} > {len(dataset)}")
				break

			# On va insérer les données  manquantes pour avoir step données initiales dans la base
			try:
				if a < step:
					mysql.create_many(dataset[a:step],silent=True)
			except Exception as e:
				mysql.logger.error(f"test_one_various_data : init error {e}")
			finally:
				a = step
		
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
			mysql.update_many({"price":0.00}, {"genre": "updated"})
			

			# On teste la suppression
			mysql.delete_many({"price":0.0})

			# On récupère les temps des opérations
			# et on ajoute les données dans le tableau
			for operation in operation_times:
				tests_data[operation].extend(operation_times[operation])
			

	except Exception as e:
		mysql.logger.error(f"test_many_various_data: error -> {e}")
	
	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,steps,plot_name,"test_many_various_data")
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
	test_function(mysql,plot_name+"_indexed",**kwargs)

def run_tests(mysql: MySQL, type_test:str, steps=arange(1000,num_records,num_records/10000)):
	
	if mysql is None:
		raise ValueError("MySQL instance is None")

	# Supprimer les index si existants
	mysql.drop_indexes()

	# Without indexes tests
	try:
		change_progression_text("Running "+type_test + "_global_one...")
		global_test_one(mysql, type_test)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_one : {e}")

	try:
		change_progression_text("Running "+type_test + "_global_many...")
		global_test_many(mysql, type_test)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_many : {e}")

	try:
		change_progression_text("Running "+type_test + "_various_one...")
		test_one_various_data(mysql, type_test,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_one_various_data : {e}")

	try:
		change_progression_text("Running "+type_test + "_various_many...")
		test_many_various_data(mysql, type_test,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_many_various_data : {e}")

	# With indexes tests
	try:
		change_progression_text("Running "+type_test + "_global_one_indexed...")
		test_indexed(mysql, type_test, global_test_one)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_one_indexed : {e}")

	try:
		change_progression_text("Running "+type_test + "_global_many_indexed...")
		test_indexed(mysql, type_test, global_test_many)
	except Exception as e:
		mysql.logger.error(f"Error with global_test_many_indexed : {e}")

	try:
		change_progression_text("Running "+type_test + "_various_one_indexed...")
		test_indexed(mysql, type_test, test_one_various_data,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_one_various_data_indexed : {e}")

	try:
		change_progression_text("Running "+type_test + "_various_many_indexed...")
		test_indexed(mysql, type_test, test_many_various_data,steps=steps)
	except Exception as e:
		mysql.logger.error(f"Error with test_many_various_data_indexed : {e}")

def change_progression_text(text:str):
	"""
	Change the text of the progression bar
	"""
	global operation_lock,operation_Event
	with operation_lock:
		print_progress.text = text
		operation_Event.clear()
		operation_Event.set()

def print_progress(total,text="Running tests..."):
	global operations_done, operation_Event, operation_lock
 
	print_progress.run = True
	percent = 0	
	with alive_bar(total=total,manual=True) as bar:
		bar.text(text)
		
		# Attendre operation_Event
		while operations_done < total and print_progress.run:
			operation_Event.wait()
			operation_Event.clear()
			with operation_lock:
				percent = operations_done/total
			bar(percent)
			bar.text(print_progress.text)
		
		bar(1.)
print_progress.run		= True
print_progress.text		="Running tests..."


def clean_exit(progress_T:Thread, mysql_clients: list[MySQL | None] | None = None):
	"""
		Arrête le thread et attend sa fin
	"""
	if mysql_clients is not None:
		for mysql in mysql_clients:
			if mysql is not None:
				mysql.close()
 
	if progress_T is not None:
		# On arrête le thread
		with operation_lock:
			print_progress.run = False
			operation_Event.clear()
			operation_Event.set()
		progress_T.join(timeout=3)
	else:
		print("End of tests")
		exit(0)

if __name__ == "__main__":

	# On affiche les informations système
	#print_system_info()

	# On charge la configuration
	get_configuration()
 
	parser = ArgumentParser(description="MySQL performance tests")
	parser.add_argument("--verbose",	help="increase output verbosity",	action="store_true")
	# Ajouter des arguments pour savoir quel(s) test(s) effectuer 
	parser.add_argument("--standalone", help="Run tests with a standalone",	action="store_true" )
	#parser.add_argument("--replica", 	help="Run tests with replica set",	action="store_true" )
	parser.add_argument("--sharded", 	help="Run tests with shards ",		action="store_true" )
	parser.add_argument("--all", 		help="Run all tests", 				action="store_true" )
 
	args = parser.parse_args()

	if (not args.standalone) and (not args.sharded) and (not args.all):
		#parser.error("No action requested, add --standalone, --replica, --sharded or --all")
		args.all = True

	# On veut nb_measurements mesures allant jusqu'à num_records.
	# Donc on prend num_records/nb_measurements comme pas et on prend comme départ :0
	steps	= arange(0,num_records,num_records/nb_measurements)
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
	#if args.replica or args.all:
	#	coeff += 1
	if args.sharded or args.all:
		coeff += 1
	# On multiplie par le nombre de tests
	total *= coeff
	
	# On crée un thread pour afficher la progression
	progress_T = Thread(target=print_progress, args=((total,)) )
	
	# On intercepte les signaux pour arrêter proprement le programme
	signal(SIGINT, lambda signum, frame: clean_exit(progress_T, [mysql_standalone, mysql_replica, mysql_sharded]))
	signal(SIGTERM, lambda signum, frame: clean_exit(progress_T, [mysql_standalone, mysql_replica, mysql_sharded]))
	
	# On démarre le thread de progression
	print("Running tests ...")
	progress_T.start()

	
	# On crée les instances de MySQL
	mysql_standalone ,mysql_replica ,mysql_sharded = None, None, None
	# On définit le niveau de log
	debug_level = DEBUG if args.verbose else INFO
	# On définit les modes d'ouverture des fichiers de logs
	alone_dbg_mode, replica_dbg_mode, sharded_dbg_mode = "w", "w", "w"
	if coeff >= 2:
		sharded_dbg_mode = "a"
		replica_dbg_mode = "a" if args.standalone else "w"

 
	if args.standalone or args.all:
		try:
			mysql_standalone = MySQL(debug_level=INFO,dbg_file_mode=alone_dbg_mode)
			change_progression_text("Tests en mode standalone...")
			run_tests(mysql_standalone, "standalone",steps=steps)
	
		except Exception as e:
			print(f"Erreur avec le test en standalone: {e}")
	
		finally:
			if mysql_standalone is not None:
				mysql_standalone.close()
	
	#if args.replica or args.all:
	#	print("No replica set tests")
		#try:
		#
		#	mysql_replica = MySQL(using_replica_set=True,debug_level=INFO,dbg_file_mode=replica_dbg_mode)
		#	change_progression_text("Tests en mode Replica...")
		#	run_tests(mysql_replica, "replica_set",steps=steps)
		#	del mysql_replica
		#
		#except Exception as e:
		#	operation_Event.clear()
		#	print(f"Erreur avec le test avec Replica Set: {e}")
		#
		#finally:
		#
		#	if mysql_replica is not None:
		#		del mysql_replica

	if args.sharded or args.all:
		try:

			mysql_sharded = MySQL(using_shard=True,debug_level=INFO,dbg_file_mode=sharded_dbg_mode)
			change_progression_text("Tests en mode Sharded...")
			run_tests(mysql_sharded, "sharding",steps=steps)

		except Exception as e:
			print(f"Erreur avec le test avec Shards: {e}")
	
		finally:
			if mysql_sharded is not None:
				mysql_sharded.close()

	# On finit le thread de progression
	with operation_lock:
		print_progress.run = False
		operation_Event.clear()
		operation_Event.set()

	progress_T.join(timeout=3)
	progress_T = None
	
	print("End of tests")
	exit(0)
# For loading environment variables
from os 		import getenv , makedirs,path, remove
from dotenv 	import load_dotenv

# for quitting the program
import atexit

# for arg parsing
from argparse import ArgumentParser

# For Mongo DB operations
from pymongo	import MongoClient, IndexModel
from pymongo	import ASCENDING, DESCENDING
# For measuring operation time
from collections import defaultdict
from pymongo	import monitoring
#from time		import perf_counter_ns
#from time		import sleep

#  For statistics
from numpy import arange, median as np_median, mean as np_mean, percentile
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

# For animation
from alive_progress import alive_bar
from threading import Thread, Lock, Event

# L'idée c'est de monitorer le temps des opérations de lecture, écriture, mise à jour et suppression
# Avec la classe MongoDB, grâce au monitoring, on peut mesurer le temps des opérations

operation_times		= defaultdict(list)
failed_operations	= dict()
system_info			= ""
operations_done		= 0
operation_lock		= Lock()
operation_Event		= Event()

"""
Collection/Table "Books" :
	id : Identifiant unique (UUID ou Auto-increment pour MySQL, ObjectId pour MongoDB)
	title : Titre du livre (String)
	author : Auteur du livre (String)
	published_date : Date de publication (Date)
	genre : Genre du livre (String)
	copies_sold : Nombre d'exemplaires vendus (Integer)
	price : Prix du livre (Float)
	ran: Champ aléatoire pour les tests entre 0 et num_records_per_many-1 (Integer)
"""

class CommandLogger(monitoring.CommandListener):
	def started(self, event):
		pass

	def succeeded(self, event):
		global operation_times

		# On ne prend pas en comptes toutes les informations
		if event.command_name not in ["delete","find","insert","update"]:
			return

		# On récupère le temps de l'opération
		operation_time = event.duration_micros
		# On récupère le nom de l'opération
		operation_name = event.command_name
		#print(f"Operation : {operation_name} - Time : {operation_time} µs")
		# On ajoute le temps de l'opération dans le tableau
		# Si l'opération n'existe pas, on la crée

		operation_times[operation_name].append(operation_time)

	def failed(self, event):
		#On compte le nombre d'opérations qui ont échoué et on stocke le nom de l'opération, la requête et le message d'erreur
		global failed_operations
		operation_name = event.command_name
		query = ""
		message = event.failure
		getLogger('pymongo').error(f"Operation failed : {operation_name} - Query : {query} - Message : {message}")

class MongoDB:

	def __init__(self,using_replica_set: bool=False,using_sharded_cluster:bool = False,debug_level:int = INFO,debug_file_mode:str = "w"):
		# Logging
		self.logger = getLogger("MongoDB")
		self.logger.setLevel(debug_level)

		# Création de fichiers de logs
		try:
			# on crée le dossier  de logs s'il n'existe pas
			makedirs("logs",exist_ok=True)

			fh 			= FileHandler('logs/mongodb-tests.log',mode=debug_file_mode)
			formatter	= Formatter(fmt="[%(levelname)s] %(filename)s:l.%(lineno)d - %(message)s")
			fh.setFormatter(formatter)
			self.logger.addHandler(fh)

			mongo_logger = getLogger('pymongo')
			fh2 		 = FileHandler('logs/mongodb.log',mode=debug_file_mode)
			fh2.setFormatter(formatter)
			mongo_logger.setLevel(debug_level)
			mongo_logger.addHandler(fh2)
		
		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
		
		# Loading Environment variables to connect to MongoDB
		try:
			load_dotenv()
			if using_replica_set:
				replica_set = getenv('MONGO_REPLICA_SET',	'rs0')
				mongo_host	= getenv('MONGO_REPLICA_HOST',	'10.0.0.10')
				mongo_port	= getenv('MONGO_REPLICA_PORT',	'27018')
			elif using_sharded_cluster:
				mongo_host	= getenv('MONGO_SHARD_HOST',	'10.0.10.10')
				mongo_port	= getenv('MONGO_SHARD_PORT',	'27019')
			else:
				mongo_host	= getenv('MONGO_HOST',			'127.0.0.1')
				mongo_port	= getenv('MONGO_PORT',			'27017')

			mongo_user	= getenv('MONGO_USER',		'')
			mongo_pass	= getenv('MONGO_PASS',		'')
			database	= getenv('MONGO_DATABASE',	'test')
			collection	= getenv('MONGO_COLLECTION','test')

		except Exception as e:
			self.logger.error(f"MongoDB.__init__: error {e}")
			raise Exception("MongoDB : Error loading environment variables")

		# Connection to MongoDB
		try:
			if using_replica_set:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											replicaSet=replica_set,
											connect=True,
											event_listeners=[CommandLogger()],
											retryWrites=True,  # Active les tentatives d'écriture automatiques
											readPreference="primary"
											#username=mongo_user,
											#password=mongo_pass
										)
			elif using_sharded_cluster:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											connect=True,
											event_listeners=[CommandLogger()],
											#directConnection=True,
											retryWrites=True,  # Active les tentatives d'écriture automatiques
											readPreference="nearest"
										)
			else:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											connect=True,
											event_listeners=[CommandLogger()],
											#directConnection=True
											#username=mongo_user,
											#password=mongo_pass
										)

			self.db			= self.client[database]
			self.collection = self.db[collection]
			self.client.server_info()
			self.client.start_session()
			self.logger.info(f"Connected to MongoDB {self.client.address[0]}:{self.client.address[1]}, Server Informations :")
			for info in self.client.server_info():
				self.logger.info(f"\t {info} : {self.client.server_info()[info]}")
		except Exception as e:
			self.logger.error(f"MongoDB.__init__: error connecting to {mongo_host}:{mongo_port} -> {e}")
			raise Exception(f"MongoDB : Error connecting to database {mongo_host}:{mongo_port} -> {e}")

	def __del__(self):
		try:
			if self.client is not None:

				self.client.close()
		except Exception as e:
			self.logger.error(f"MongoDB.__del__: {e}")
	
	def __update_operation_count(self):
		global operations_done, operation_Event, operation_lock
		with operation_lock:
			operations_done += 1
			operation_Event.clear()
			operation_Event.set()

	def create_index(self,field ,unique : bool=False):
		"""
		Create an index on the field
		:param field: the field to index
		"""
		try:
			if self.collection.create_index(field,unique=unique) is not None:
				self.logger.debug(f"Index created : {field}")
			else:
				self.logger.error(f"MongoDB.create_index : Error creating index : {field}")
		except Exception as e:
			self.logger.error(f"MongoDB.create_index : {e}")

	def create_indexes(self,fields:list[IndexModel]):
		"""
		Create indexes on the fields
		:param fields: the fields to index
		"""
		try:
			if self.collection.create_indexes(fields) is not None:
				self.logger.debug(f"Indexes created : {fields}")
			else:
				self.logger.error(f"MongoDB.create_indexes : No index created among {fields}")
		except Exception as e:
			self.logger.error(f"MongoDB.create_indexes : Error creating indexes -> {e}")

	def drop_indexes(self):
		"""
		Delete all indexes in the collection
		"""
		try:
			self.collection.drop_indexes()
		except Exception as e:
			self.logger.error(f"Error dropping indexes : {e}")
	
	def read(self,print_result: bool = True)-> list:
		"""
		Find all documents in the collection
		"""
		self.__update_operation_count()
		l = []
		try:
			for x in self.collection.find():
				if print_result:
					self.logger.debug(x)
				l.append(x)
		except Exception as e:
			self.logger.error(f"Error reading data : {e}")
		finally:
			return l

	def read_one(self,query,print_result:bool = True):
		"""
		Find the first document that matches the query
		:param query: the query to find the document
		"""
		self.__update_operation_count()
		try:
			x = self.collection.find_one(query)
		except Exception as e:
			self.logger.error(f"Error reading one data : {e}")
		if print_result:
			self.logger.debug(x)
		return x

	def read_many(self,query,print_result:bool = True):
		"""
		Find all documents that match the query
		:param query: the query to find the documents
		"""
		self.__update_operation_count()
		l = []
		try:
			for x in self.collection.find(query):
				if print_result:
					self.logger.debug(x)
				l.append(x)
			if len(l) == 0:
				self.logger.warning(f"No data found with : {query}")
				# Dans ce cas, on va afficher les champs de données de la base collection
				# pour voir si on a des données
				self.logger.info(f"Fields : {self.collection.find_one()}")

		except Exception as e:
			self.logger.error(f"Error reading many data : {e}")
		finally:
			return l

	def create_one(self,data,silent=False):
		"""
		Insert one document in the collection
		:param data: the document to insert
		"""
		if not silent:
			self.__update_operation_count()
		try:
			if self.collection.insert_one(data) :
				self.logger.debug(f"Data inserted : {data}")
			else:
				self.logger.error(f"Error inserting data : {data}")
		except Exception as e:
			self.logger.error(f"Error inserting one data : {e}")

	def update_one(self,query,new_values):
		"""
		Modify the first document that matches the query
		:param query: the query to find the document to update
		:param new_values: the new values to update
		"""
		self.__update_operation_count()
		try:
			update_result = self.collection.update_one(query, new_values)
		except Exception as e:
			self.logger.error(f"Error updating one data : {e}")
		if update_result.modified_count > 0:
			self.logger.debug(f"Data updated : {query} -> {new_values}")
		elif update_result.matched_count > 0:
			self.logger.error(f"No data updated but {update_result.matched_count} matched with \n: \t \t{query} -> {new_values}")
		else:
			self.logger.error(f"No data updated with : {query} -> {new_values}")

	def delete_one(self,query):
		"""
		Delete the first document that matches the query
		:param query: the query to find the document to delete
		"""
		self.__update_operation_count()
		try:
			if self.collection.delete_one(query).deleted_count > 0:
				self.logger.debug(f"Data deleted : {query}")
			else:
				self.logger.warning(f"No data deleted with : {query}")
		except Exception as e:
			self.logger.error(f"Error deleting one data : {e}")
	
	# Operations with several documents
	def create_many(self,data,silent=False):
		"""
		Insert several documents in the collection
		:param data: the documents to insert
		"""
		if not silent:
			self.__update_operation_count()
		try:
			if self.collection.insert_many(data):
				self.logger.debug(f"Data inserted : {data}")
			else:
				self.logger.error(f"Error inserting many data : {data}")
		except Exception as e:
			self.logger.error(f"Error inserting many data : {e}")

	def update_many(self,query,new_values):
		"""
		Modify all documents that match the query
		:param query: the query to find the documents to update
		:param new_values: the new values to update
		"""
		self.__update_operation_count()
		try:
			update_result = self.collection.update_many(query, new_values)
		except Exception as e:
			self.logger.error(f"Error updating many data : {e}")
		if update_result.modified_count > 0:
			self.logger.debug(f" { update_result.modified_count} Data updated : {query} -> {new_values}")
		elif update_result.matched_count > 0:
			self.logger.error(f"No data updated but {update_result.matched_count} matched with \n: \t \t{query} -> {new_values}")
		else:
			self.logger.error(f"No data updated with : {query} -> {new_values}")

	def delete_many(self,query):
		"""
		Delete all documents that match the query
		:param query: the query to find the documents to delete
		"""
		self.__update_operation_count()
  
		try:
			if self.collection.delete_many(query).deleted_count > 0:
				self.logger.debug(f"Data deleted : {query}")
			else:
				self.logger.debug(f"No data deleted with : {query}")
		except Exception as e:
			self.logger.error(f"Error deleting many data : {e}")
	
	def clear_operation_data(self):
		"""
		Clear the times of the operations
		"""
		global operation_times
		operation_times.clear()
		
	def drop_all(self):
		"""
		Delete all documents in the collection
		"""
		try:
			self.delete_many({})
		except Exception as e:
			self.logger.error(f"Error dropping all data : {e}")

	def close(self):
		self.client.close()


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
	makedirs(f"plots/MongoDB/{test_type}/{test_name}", exist_ok=True)
 
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in operation_times:

		if isinstance(operation_times[operation],list):
			data = operation_times[operation]
		else:
			data = [operation_times[operation]]
	

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
		mean	= np_mean(data)
		

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

		if path.exists(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png"):
			remove(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png")
		plt.savefig(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png")

		# On réinitialise le graphique
		plt.clf()

		# on ferme la figure
		plt.close()	

def plot_operation_times( data : dict, steps, test_type="test",test_name=""):
	"""
		Affiche le temps des opérations selon la quantité de données dans la base de données
	"""

	# On crée un dossier pour les graphiques
	makedirs(f"plots/MongoDB/{test_type}/{test_name}", exist_ok=True)
	
	# On va créer un graphique pour chaque opération, on affiche que l'opération courante
	for operation in data:
		
		# Calcul des stats : médiane, moyenne et quartiles		
		moyenne	= np_mean(data[operation])
		mediane	= np_median(data[operation])
		q1		= percentile(data[operation], 25)
		q3		= percentile(data[operation], 75)

		# On affiche le temps moyen en µs en fonction de la quantité de données
		plt.plot(steps,data[operation], label=f"{operation} : µs" )
	
		# On trace les lignes de moyenne, médiane et quartiles
		plt.axhline(y=moyenne, color='r', linestyle='--', label=f'Moyenne : {moyenne:.2f} µs')
		plt.axhline(y=mediane, color='g', linestyle='--', label=f'Médiane : {mediane:.2f} µs')
		plt.axhline(y=q1, color='b', linestyle='--', label=f'Quartiles 1 (25%) : {q1:.2f} µs')
		plt.axhline(y=q3, color='b', linestyle='--', label=f'Quartiles 3 (75%) : {q3:.2f} µs')
  
		# on ajoute dans la légende les couleurs des lignes et les labels
		legend_elements = [
			Line2D([0], [0], color='r', linestyle='--', label=f'Moyenne : {moyenne:.2f} µs'),
			Line2D([0], [0], color='g', linestyle='--', label=f'Médiane : {mediane:.2f} µs'),
			Line2D([0], [0], color='b', linestyle='--', label=f'Quartiles 1 (25%) : {q1:.2f} µs'),
			Line2D([0], [0], color='b', linestyle='--', label=f'Quartiles 3 (75%) : {q3:.2f} µs'),
		]
		
		# Personnalisation du graphique
		plt.title(f"{operation} : Temps d'execution en fonction de la quantité de données")
		plt.xlabel("Données dans la base de données")
		plt.ylabel('Time (µs)')
		plt.legend(handles=legend_elements, loc='best' )

		# On sauvegarde la figure
		if path.exists(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png"):
			remove(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png")
		plt.savefig(f"plots/MongoDB/{test_type}/{test_name}/{operation}.png")
	
		# On réinitialise le graphique
		plt.clf()
  
		# on ferme la figure
		plt.close()
	
	if len(data) == 0:
		print("No data to plot")


######### Tests de performance #########

def global_test_one(mongo: MongoDB,plot_name :str ,  nb_data:int = num_records):
	global num_records_per_many, generated_file, updated_file
 
	mongo.logger.info("Test global one by one " + plot_name)
 
	if nb_data < 0:
		raise ValueError("nb_data must be > 0 and <= " + str(num_records))

	# On récupère les données
	dataset = extract_books_from_file(generated_file,nb_data)

	if len(dataset) < nb_data:
		mongo.logger.warning(f"Gathered {len(dataset)} records instead of {nb_data}")
 
	nb_data = len(dataset)
	
	### Tests avec données une par une  ###
 
	## Test d'insertion de données
	for book in dataset:
		mongo.create_one(book)

	# Libérer la mémoire
	dataset.clear()
 
	## Test de lecture de données sur la collection "Books", en choississant l'id
	for i in range(0,nb_data):
		mongo.read_one({"id":i},print_result=False)

	## Test de mise à jour de données
 
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
	
	for update in updated_dataset:
		original = update[0]
		modified = update[1]
	
		if original == modified:
			mongo.logger.error(f"Data are the same : \n\t{original} -> \n\t{modified}")
		else:
			#Sinon on identifie le champ modifié
			new_values = {}
			key = ""
			for key in original:
				if original[key] != modified[key]:
					new_values = {key: modified[key]}
					break
			mongo.update_one(update[0],{ "$set": new_values})
			

	## Test de suppression de données
	mongo.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mongo.delete_one(book)

	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name,"global_test_one")
	except Exception as e:
		mongo.logger.error(f"global_test_one : error plotting -> {e}")

	
	# Afficher les opérations qui ont échoué
	#print_failed_operations()
 
	# On supprime toutes les données de la collection
	mongo.drop_all()	
 
	# On réinitialise les données des opérations
	mongo.clear_operation_data()

def global_test_many(mongo: MongoDB,plot_name :str, nb_data:int = num_records):
	global updated_file, generated_file, num_records_per_many, num_records

	mongo.logger.info("Test global many " + plot_name)

	### Tests avec plusieurs données à la fois  ###
	
	if nb_data  < 0: 
		raise ValueError("nb_data must be > 0 and <= " + str(num_records_per_many))

	# On récupère les données
	dataset = extract_books_from_file(generated_file,nb_data)

	if len(dataset) < nb_data:
		mongo.logger.warning(f"Gathered {len(dataset)} records instead of {nb_data}")
	
	nb_data = len(dataset)
	
	# On envoie à chaque fois num_records_per_many données
	
	## Test d'insertion de données
	for i in range(0,nb_data,num_records_per_many):
		#data = [book for book in dataset[i:i+num_records_per_many]]
		mongo.create_many(dataset[i:i+num_records_per_many],silent=True)

	# vide dataset pour libérer la mémoire
	dataset.clear()
 
	## Test de mise à jour de données
	
	# Chargement des données à modifier
	#updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
 
	for i in range(0,num_records_per_many):
		# On met à jour les données
		# Avec le champ "ran" qui est entre O  
		mongo.update_many({"ran" : i%num_records_per_many},{ "$inc": {"price" : 5.00, "copies_sold": 100} } )

	dataset.clear()
 
	## Test de lecture de données
	for i in range(0,num_records_per_many):
		mongo.read_many({"ran" : i},print_result=False)

	## Test de suppression de données
	for i in range(0,num_records_per_many):
		# On supprime les données
		mongo.delete_many({"ran" : i})


	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name,"global_test_many")
	except Exception as e:
		mongo.logger.error(f"global_test_many : error plotting -> {e}")
	
	# Afficher les opérations qui ont échoué
	#print_failed_operations()
 
	# On supprime toutes les données de la collection
	mongo.drop_all()
 
	# On réinitialise les données des opérations
	mongo.clear_operation_data()

def test_one_various_data(mongo: MongoDB,plot_name :str, steps=arange(1000,num_records,num_records/10000)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
 	"""
	global operation_times, generated_file

	mongo.logger.info("Test one by one with various data "+ plot_name)
	
	# On supprime toutes les données de la collection s'il y en a
	mongo.drop_all()
 
	# On extrait toutes les données dont on aura besoin
	dataset = extract_books_from_file(generated_file,steps[-1])
	if len(dataset) < steps[-1]:
		mongo.logger.warning(f"Gathered {len(dataset)} records instead of {step}")
	
	tests_data = defaultdict(list)

	try:
		a=0
		for step in steps:
			step = int(step)

			# On arrête si on dépasse le nombre de données disponibles
			if step > len(dataset):
				mongo.logger.warning(f"Step {step} > {len(dataset)}")
				break

			# On va insérer les données  manquantes pour avoir step données initiales dans la base
			try:
				if a < step:
					mongo.create_many(dataset[a:step],silent=True)
			except Exception as e:
				mongo.logger.error(f"test_one_various_data : {e}")
			finally:
				a = step

			# On nettoie les temps des opérations, 
			# pour recommencer les mesures
			operation_times.clear()

			# On procède au test de performance
			max_id 			 = step +1
			generate_book.id = max_id
			book = generate_book(max_id)

			# On nettoie les temps des opérations, 
			# pour recommencer les mesures
			operation_times.clear()
			
			# On teste l'insertion
			mongo.create_one(book)

			# On teste la lecture
			mongo.read_one({"id":book["id"]})

			# On teste la mise à jour
			new_book = modify_book(book)
			mongo.update_one({"id":book["id"]}, {"$set": new_book})
		
			# On teste la suppression
			mongo.delete_one({"id":book["id"]})

			# On récupère les temps des opérations et 
			# On ajoute les données dans le tableau
			for operation in operation_times:
				tests_data[operation].extend(operation_times[operation])

	except Exception as e:
		mongo.logger.error(f"test_one_various_data : operation error -> {e}")

	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,steps,plot_name,"test_one_various_data")
	except Exception as e:
		mongo.logger.error(f"test_one_various_data : error plotting -> {e}")
 
	# On supprime toutes les données de la collection
	mongo.drop_all()

def test_many_various_data(mongo: MongoDB,plot_name :str, steps=arange(1000,num_records,num_records/10000)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
	"""
	global operation_times, generated_file
 
	mongo.logger.info("Test many with various data " + plot_name)

	# On supprime toutes les données de la collection s'il y en a
	mongo.drop_all()
 
	# On extrait toutes les données dont on aura besoin
	dataset = extract_books_from_file(generated_file,steps[-1])
	if len(dataset) < steps[-1]:
		mongo.logger.warning(f"Gathered {len(dataset)} records instead of {step}")

	tests_data = defaultdict(list)
	try:
		a=0
		for step in steps:
			step = int(step)

			# On arrête si on dépasse le nombre de données disponibles
			if step > len(dataset):
				mongo.logger.warning(f"Step {step} > {len(dataset)}")
				break

			# On va insérer les données  manquantes pour avoir step données initiales dans la base
			try:
				if a < step:
					mongo.create_many(dataset[a:step],silent=True)
			except Exception as e:
				mongo.logger.error(f"test_one_various_data : {e}")
			finally:
				a = step
	
			## On procède au test de performance

			# Génère les données à insérer
			max_id			 = step + 1
			generate_book.id = max_id
			books = [generate_book(max_id + i) for i in range(0,num_records_per_many)]

			# Modifie le prix à 0 pour la suppression/lecture exacte de num_records_per_many données
			# en effet un prix à 0 est impossible pour un livre, ce seront donc les données à supprimer
			for book in books:
				book["price"] = 0.0

			# On nettoie les temps des opérations, 
			# pour prendre les mesures
			operation_times.clear()

			# On teste l'insertion
			mongo.create_many(books)

			# On teste la lecture
			mongo.read_many({"price":0.0})

			# On teste la mise à jour
			mongo.update_many({"price":0.00}, {"$set": {"genre": "updated"} })
	
			# On teste la suppression
			mongo.delete_many({"price":0.0, "genre": "updated"})

			# Après ces opérations, on est revenu à l'état initial
			# On a juste les données ajoutées initialement dans la base avant les tests
	
			# On récupère les temps des opérations et
			# on ajoute les données dans le tableau
			for operation in operation_times:
				tests_data[operation].extend(operation_times[operation])

	except Exception as e:
		mongo.logger.error(f"test_many_various_data : operation error -> {e}")

	# On dessine les graphiques
	try:
		plot_operation_times(tests_data,steps,plot_name,"test_many_various_data")
	except Exception as e:
		mongo.logger.error(f"test_many_various_data: error plotting -> {e}")
  
	# On supprime toutes les données de la collection	
	mongo.drop_all()

def test_indexed(mongo: MongoDB,plot_name :str, test_function,**kwargs):
	# On définit les index
	indexes = [ IndexModel("title"),
				IndexModel("author"),
				IndexModel("published_date"),
				IndexModel("genre"),
				IndexModel("copies_sold"),
				IndexModel("ran")
			  ]
	mongo.logger.debug("Creating indexes...")
 
	# On efface tous les index existants
	mongo.drop_indexes()
 
	# On distingue id des autres index car id est utilisé pour le sharding
	try:
		mongo.create_index("id",unique=True)
	except Exception as e:
		mongo.logger.error(f"Error creating indexes : {e}")

	# On crée les index
	mongo.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test_function(mongo,plot_name,**kwargs)

def run_tests(mongo: MongoDB, type_test:str, steps=arange(1000,num_records,num_records/10000)):
	
	if mongo is None:
		raise ValueError("MongoDB instance is None")

	# Supprimer les index si existants
	mongo.drop_indexes()

	# Without indexes tests
	try:
		print_progress.text = "Running "+type_test + "_global_one..."
		global_test_one(mongo, type_test)
	except Exception as e:
		mongo.logger.error(f"Error with global_test_one : {e}")

	try:
		print_progress.text = "Running"+type_test + "_global_many..."
		global_test_many(mongo, type_test)
	except Exception as e:
		mongo.logger.error(f"Error with global_test_many : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_one..."
		test_one_various_data(mongo, type_test,steps=steps)
	except Exception as e:
		mongo.logger.error(f"Error with test_one_various_data : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_many..."
		test_many_various_data(mongo, type_test,steps=steps)
	except Exception as e:
		mongo.logger.error(f"Error with test_many_various_data : {e}")

	# With indexes tests
	try:
		print_progress.text = "Running "+type_test + "_global_one_indexed..."
		test_indexed(mongo, type_test, global_test_one)
	except Exception as e:
		mongo.logger.error(f"Error with global_test_one_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_global_many_indexed..."
		test_indexed(mongo, type_test + "_indexed", global_test_many)
	except Exception as e:
		mongo.logger.error(f"Error with global_test_many_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_one_indexed..."
		test_indexed(mongo, type_test + "_indexed", test_one_various_data,steps=steps)
	except Exception as e:
		mongo.logger.error(f"Error with test_one_various_data_indexed : {e}")

	try:
		print_progress.text = "Running "+type_test + "_various_many_indexed..."
		test_indexed(mongo, type_test + "_indexed", test_many_various_data,steps=steps)
	except Exception as e:
		mongo.logger.error(f"Error with test_many_various_data_indexed : {e}")



def print_progress(total,text="Running tests..."):
	global operations_done, operation_Event, operation_lock
 
	with alive_bar(total=total,manual=True) as bar:
		bar.text(text)
		print_progress.run = True
		# Attendre operation_Event
		while operations_done < total and print_progress.run:
			operation_Event.wait()
			operation_Event.clear()
			with operation_lock:
				percent = operations_done/total
			bar(percent)
			bar.text(print_progress.text)

		bar(1.)
		bar.text(f"Operations done !")
print_progress.run		= True
print_progress.text		="Running tests..."


if __name__ == "__main__":

	# On affiche les informations système
	#print_system_info()

	# On charge la configuration
	get_configuration()
 
	parser = ArgumentParser(description="MongoDB performance tests")
	parser.add_argument("--verbose",	help="increase output verbosity",	action="store_true")
	# Ajouter des arguments pour savoir quel(s) test(s) effectuer 
	parser.add_argument("--standalone", help="Run tests with a standalone",			action="store_true" )
	parser.add_argument("--replica", 	help="Run tests with replica set",			action="store_true" )
	parser.add_argument("--sharded", 	help="Run tests with shards ",				action="store_true" )
	parser.add_argument("--all", 		help="Run tests with all configurations",	action="store_true" )


	args = parser.parse_args()

	if (not args.standalone) and (not args.replica) and (not args.sharded) and (not args.all):
		#parser.error("No action requested, add --standalone, --replica, --sharded or --all")
		args.all = True

	# On part avec O données initiales et on veut 100 mesures intermédiaires jusqu'à num_records
	# On aura donc un besoin d'un pas de (num_records - 0)/nb_measurements
	steps	= arange(0,num_records,num_records/nb_measurements,dtype=int)
	size 	= len(steps) # Nombre de mesures intermédiaires : nb_measurements
 
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
	
	# On crée les instances de MongoDB
	mongo_standalone, mongo_replica, mongo_sharded =  None, None, None
	
	# On définit le niveau de log
	debug_level = DEBUG if args.verbose else INFO
	# On définit le mode d'écriture du fichier de log selon les tests à effectués (on se base sur le coeff)
	alone_dbg_mode, replica_dbg_mode, sharded_dbg_mode = "w", "w", "w"
	if coeff >= 2:
		sharded_dbg_mode = "a+"
		replica_dbg_mode = "a+" if args.standalone else "w"
  
	if args.standalone or args.all:
		try:

			mongo_standalone = MongoDB(debug_level=debug_level,debug_file_mode=alone_dbg_mode)
			print_progress.text = "Tests en mode standalone..."
			run_tests(mongo_standalone, "standalone" ,steps=steps)

		except Exception as e:
			print(f"Erreur avec le test en standalone: {e}")
   
		finally:
			if mongo_standalone is not None:
				del mongo_standalone
	
	if args.replica or args.all:
		try:

			mongo_replica = MongoDB(using_replica_set=True,debug_level=debug_level,debug_file_mode=alone_dbg_mode)
			print_progress.text = "Tests en mode Replica..."
			run_tests(mongo_replica, "replica_set", steps=steps)

		except Exception as e:

			print(f"Erreur avec le test avec Replica Set: {e}")

		finally:

			if mongo_replica is not None:
				del mongo_replica

	if args.sharded or args.all:
		try:

			mongo_sharded = MongoDB(using_sharded_cluster=True,debug_level=debug_level,debug_file_mode=alone_dbg_mode)
			print_progress.text = "Tests en mode Sharded..."
			run_tests(mongo_sharded, "sharding", steps=steps)

		except Exception as e:

			print(f"Erreur avec le test avec Shards: {e}")

		finally:
			if mongo_sharded is not None:
				del mongo_sharded

	# On finit le thread de progressions
	print_progress.run = False
	operation_Event.set()
	progress_T.join(timeout=3)
	
	print("End of tests !")
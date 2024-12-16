# For loading environment variables
from os 		import getenv , makedirs
from dotenv 	import load_dotenv
# For Mongo DB operations
from pymongo	import MongoClient, IndexModel
# For measuring operation time
from pymongo	import monitoring
#from time		import perf_counter_ns
#from time		import sleep

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

# L'idée c'est de monitorer le temps des opérations de lecture, écriture, mise à jour et suppression
# Avec la classe MongoDB, grâce au monitoring, on peut mesurer le temps des opérations

operation_times		= {}
failed_operations	= {}
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

		# On ne prend pas en compte les commandes de buildinfo et endSessions
		if event.command_name in ["buildinfo","endSessions","createIndexes"]:
			return
   
		# On récupère le temps de l'opération
		operation_time = event.duration_micros
		# On récupère le nom de l'opération
		operation_name = event.command_name
		#print(f"Operation : {operation_name} - Time : {operation_time} µs")
		# On ajoute le temps de l'opération dans le tableau
		if operation_name not in operation_times:
			operation_times[operation_name] = [operation_time]
		else:
			operation_times[operation_name].append(operation_time)

	def failed(self, event):
		#On compte le nombre d'opérations qui ont échoué et on stocke le nom de l'opération, la requête et le message d'erreur
		global failed_operations
		operation_name = event.command_name
		query = ""
		message = event.failure
		getLogger('pymongo').error(f"Operation failed : {operation_name} - Query : {query} - Message : {message}")

class MongoDB:

	def __init__(self,using_replica_set: bool=False,using_sharded_cluster:bool = False,debug_level:int = INFO):
		# Logging
		self.logger = getLogger("MongoDB")
		self.logger.setLevel(debug_level)
		try:
			# on crée le dossier  de logs s'il n'existe pas
			makedirs("logs",exist_ok=True)
			self.logger.addHandler(FileHandler('logs/mongodb-tests.log'))

			mongo_logger = getLogger('pymongo')
			mongo_logger.setLevel(debug_level)
			mongo_logger.addHandler(FileHandler('logs/mongodb.log'))
		
		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
		
		# Loading Environment variables to connect to MongoDB
		try:
			load_dotenv()
			if using_replica_set:
				replica_set = getenv('MONGO_REPLICA_SET',	'rs0')
				mongo_host	= getenv('MONGO_REPLICA_HOST',	'localhost')
				mongo_port	= getenv('MONGO_REPLICA_PORT',	'27018')
			elif using_sharded_cluster:
				mongo_host	= getenv('MONGO_SHARD_HOST',	'localhost')
				mongo_port	= getenv('MONGO_SHARD_PORT',	'27019')
			else:
				mongo_host	= getenv('MONGO_HOST',			'localhost')
				mongo_port	= getenv('MONGO_PORT',			'27017')

			mongo_user	= getenv('MONGO_USER',		'')
			mongo_pass	= getenv('MONGO_PASS',		'')
			database	= getenv('MONGO_DATABASE',	'test')
			collection	= getenv('MONGO_COLLECTION','test')

		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
			raise Exception("MongoDB : Error loading environment variables")

		# Connection to MongoDB
		try:
			if using_replica_set:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											replicaSet=replica_set,
											connect=True,
											event_listeners=[CommandLogger()],
											directConnection=True
											#username=mongo_user,
											#password=mongo_pass
										)
			elif using_sharded_cluster:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											connect=True,
											event_listeners=[CommandLogger()],
											directConnection=True
										)
			else:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											connect=True,
											event_listeners=[CommandLogger()]
											#username=mongo_user,
											#password=mongo_pass
										)

			self.db			= self.client[database]
			self.collection = self.db[collection]
			self.client.server_info()
			self.client.start_session()
			self.logger.info("Connected to MongoDB")

		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
			raise Exception("MongoDB : Error connecting to database")

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
				self.logger.error(f"Error creating indexes : {fields}")
		except Exception as e:
			self.logger.error(f"Error creating indexes : {e}")

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
				self.logger.error(f"No data deleted with : {query}")
		except Exception as e:
			self.logger.error(f"Error deleting one data : {e}")
	
	# Operations with several documents
	def create_many(self,data):
		"""
		Insert several documents in the collection
		:param data: the documents to insert
		"""
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
			#else:
			#	self.logger.error(f"No data deleted with : {query}")
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

def violin_plot_operation_times(test_name=""):
	"""
	Plot the times of the operations
	"""
	global operation_times
	
	# On crée un dossier pour les graphiques
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
	mongo.logger.debug("Test insert one by one : ")
	for book in dataset:
		mongo.create_one(book.__dict__)

	# Libérer la mémoire
	dataset.clear()
 
	## Test de lecture de données sur la collection "Books", en choississant l'id
	mongo.logger.debug("Test read one by one : ")
	for i in range(0,nb_data):
		mongo.read_one({"id":i},print_result=False)

	## Test de mise à jour de données
 
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
	
	for update in updated_dataset:
		original = update[0].__dict__
		modified = update[1].__dict__
	
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
			mongo.update_one(update[0].__dict__,{ "$set": new_values})
			

	## Test de suppression de données
	mongo.logger.debug("Test delete one by one : ")
	for _,book in updated_dataset:
		mongo.delete_one(book.__dict__)

	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name)
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

	mongo.logger.info("Test global many" + plot_name)

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
	mongo.logger.debug("Test insert many : ")
	for i in range(0,nb_data,num_records_per_many):
		data = [book.__dict__ for book in dataset[i:i+num_records_per_many]]
		mongo.create_many(data)

	# vide dataset pour libérer la mémoire
	dataset.clear()
 
	## Test de mise à jour de données
	
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file,nb_data)
	# note : update_dataset contains the original and modified data
 
	mongo.logger.debug("Test update many : ")
	for i in range(0,len(updated_dataset),num_records_per_many):
		# On met à jour les données
		# Avec le champ "ran" qui est entre O  
		mongo.update_many({"ran" : i %num_records_per_many},{ "$inc": {"price" : 5.00, "copies_sold": 100} } )

	dataset.clear()
 
	## Test de lecture de données
	mongo.logger.debug("Test read all : ")
	mongo.read(print_result=False)

	## Test de suppression de données
	mongo.logger.debug("Test delete many : ")
	for i in range(0,num_records_per_many):
		# On supprime les données
		mongo.delete_many({"ran" : i})


	# Dessiner les graphiques
	try:
		violin_plot_operation_times(plot_name)
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
	
	tests_data = {}
	for step in steps:
		
		# On supprime toutes les données de la collection s'il y en a
		mongo.drop_all()

		# On va extraire les données, pour opérer sur les mêmes données
		dataset = extract_books_from_file(generated_file,step)
		if len(dataset) < step:
			mongo.logger.error(f"Gathered {len(dataset)} records instead of {step}")

		# On va insérer les données
		max_id = 0
		for book in dataset:
			mongo.create_one(book.__dict__,silent=True)
			if book.id > max_id:
				max_id = book.id + 1

		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations, 
		# pour recommencer les mesures
		operation_times.clear()

		# On procède au test de performance
		generate_book.id = max_id
		book = generate_book(max_id)
		# Pour la mise à jour
		new_book = modify_book(book)
		

		# On teste l'insertion
		mongo.create_one(book)

		# On teste la lecture
		mongo.read_one({"id":book["id"]})


		mongo.update_one({"id":book["id"]}, {"$set": new_book})
	
		# On teste la suppression
		mongo.delete_one({"id":book["id"]})

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
		mongo.logger.error(f"test_one_various_data : error plotting -> {e}")
 
	# On supprime toutes les données de la collection
	mongo.drop_all()

def test_many_various_data(mongo: MongoDB,plot_name :str, steps=arange(1000,num_records,num_records/10000)):
	"""
		On teste le temps des opérations avec différentes quantités de données initiales dans la base de données
	"""
	global operation_times, generated_file
 
	mongo.logger.info("Test many with various data " + plot_name)

	tests_data = {}
	for step in steps:
		
		# On supprime toutes les données de la collection s'il y en a
		mongo.drop_all()

		# On va extraire les données, pour opérer sur les mêmes données
		dataset = extract_books_from_file(generated_file,step)
  
		if len(dataset) < step:
			mongo.logger.error(f"Gathered {len(dataset)} records instead of {step}")
			break

		# On va insérer les données
		max_id = 0
		for book in dataset:
			mongo.create_one(book.__dict__,silent=True)
			if book.id> max_id:
				max_id = book.id + 1 

		# On nettoie dataset pour libérer la mémoire
		dataset.clear()
		
		# On nettoie les temps des opérations, 
		# pour recommencer les mesures
		operation_times.clear()

		## On procède au test de performance

		# Génère les données à insérer
		generate_book.id 	= max_id

		books = [generate_book(max_id + i) for i in range(0,num_records_per_many)]
		# Modifie le prix à 0 pour la suppression/lecture exacte de num_records_per_many données
		# en effet un prix à 0 est impossible pour un livre, ce seront donc les données à supprimer
		for i in range(0,len(books)):
			books["price"] = 0.0

		# On teste l'insertion
		mongo.create_many([book for book in books])

		# On teste la lecture
		mongo.read_many({"price":0.0})

		# On teste la mise à jour
		mongo.update_many({"price":0.00}, {"$set": {"genre": "updated"} })
	
		# On teste la suppression
		mongo.delete_many({"price":0.0})

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
		mongo.logger.error(f"test_many_various_data: error plotting -> {e}")
  
	# On supprime toutes les données de la collection	
	mongo.drop_all()

def test_indexed(mongo: MongoDB,plot_name :str, test_function,**kwargs):
	# On définit les index
	indexes = [	IndexModel("id", unique=True), 
				IndexModel("title"), 
				IndexModel("author"), 
				IndexModel("published_date"), 
				IndexModel("genre"), 
				IndexModel("copies_sold"),
				IndexModel("ran")]
	mongo.logger.debug("Creating indexes...")
	# On efface les index si existants
	mongo.drop_indexes()
	# On crée les index
	mongo.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test_function(mongo,plot_name,**kwargs)

def run_tests(mongo: MongoDB, type_test:str):
	# Without indexed tests
	try:
		if mongo is None:
			raise ValueError("MongoDB instance is None")

		# Supprimer les index si existants
		mongo.drop_indexes()
		try:
			print_progress.text = "Running "+type_test + "_global_one..."
			global_test_one(mongo, type_test + "_global_one")
		except Exception as e:
			mongo.logger.error(f"Error with global_test_one : {e}")
		#try:
		#	print_progress.text = "Running"+type_test + "_global_many..."
		#	global_test_many(mongo, type_test + "_global_many")
		#except Exception as e:
		#	mongo.logger.error(f"Error with global_test_many : {e}")
		try:
			print_progress.text = "Running "+type_test + "_various_one..."
			test_one_various_data(mongo, type_test + "_various_one")
		except Exception as e:
			mongo.logger.error(f"Error with test_one_various_data : {e}")
		#try:
		#	print_progress.text = "Running "+type_test + "_various_many..."
		#	test_many_various_data(mongo, type_test + "_various_many")
		#except Exception as e:
		#	mongo.logger.error(f"Error with test_many_various_data : {e}")
   
   
		# With indexed tests
		try:
			print_progress.text = "Running "+type_test + "_global_one_indexed..."
			test_indexed(mongo, type_test + "_global_one_indexed", global_test_one)
		except Exception as e:
			mongo.logger.error(f"Error with global_test_one_indexed : {e}")
		#try:
		#	print_progress.text = "Running "+type_test + "_global_many_indexed..."
		#	test_indexed(mongo, type_test + "_global_many_indexed", global_test_many)
		#except Exception as e:
		#	mongo.logger.error(f"Error with global_test_many_indexed : {e}")
		try:
			print_progress.text = "Running "+type_test + "_various_one_indexed..."
			test_indexed(mongo, type_test + "_various_one_indexed", test_one_various_data)
		except Exception as e:
			mongo.logger.error(f"Error with test_one_various_data_indexed : {e}")
		#try:
		#	print_progress.text = "Running "+type_test + "_various_many_indexed..."
		#	test_indexed(mongo, type_test + "_various_many_indexed", test_many_various_data)
		#except Exception as e:
		#	mongo.logger.error(f"Error with test_many_various_data_indexed : {e}")
  
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
	
	steps = arange(1000,num_records,num_records/10)
	size 	= len(steps)
	del steps
 
	total_test_various = 8 * size + 8 * size
	total_test_one	= 16 * num_records
	total_test_many = 16 * num_records/num_records_per_many
	total 			= int(total_test_various + total_test_one + total_test_many )
	

	
	progress_T = Thread(target=print_progress, args=((total,)) )
	progress_T.start()
	
	errors = ""
	
	try:
		mongo_standalone = MongoDB(debug_level=INFO)
		print_progress.text = "Tests en mode standalone..."
		run_tests(mongo_standalone, "single_instance")
	except Exception as e:
		print(f"Erreur avec le test en standalone: {e}")
		errors += f"Erreur avec le test en standalone: {e}\n"
	finally:
		if mongo_standalone is not None:
			del mongo_standalone
	

	try:
		mongo_replica = MongoDB(using_replica_set=True,debug_level=INFO)
		print_progress.text = "Tests en mode Replica..."
		#run_tests(mongo_replica, "replica_set")
	except Exception as e:
		print(f"Erreur avec le test avec Replica Set: {e}")
		errors += f"Erreur avec le test avec Replica Set: {e}\n"
	finally:
		if mongo_replica is not None:
			del mongo_replica
  
	try:
		mongo_sharded = MongoDB(using_sharded_cluster=True,debug_level=INFO)
		print_progress.text = "Tests en mode Sharded..."
		#run_tests(mongo_sharded, "sharding")
	except Exception as e:
		print(f"Erreur avec le test avec Shards: {e}")
		errors += f"Erreur avec le test avec Shards: {e}\n"
	finally:
		if mongo_sharded is not None:
			del mongo_sharded
  
	# On finit le thread de progressions
	print_progress.run = False
	operation_Event.set()
	progress_T.join(timeout=1)
	
	print("End of tests")
	print(errors)
	

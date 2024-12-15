# For loading environment variables
from os 		import getenv
from dotenv 	import load_dotenv
# For Mongo DB operations
from pymongo	import MongoClient, IndexModel
# For measuring operation time
from pymongo	import monitoring
#from time		import perf_counter_ns

# For generating data and handling data
from data_generation import extract_books_from_file, extract_updated_books_from_file, Book
from data_generation import num_records, num_records_per_many, generated_file, updated_file

# for graphing
import matplotlib.pyplot as plt

# For system information
from platform import system, release, machine, architecture, python_version
from psutil import cpu_count, virtual_memory
from cpuinfo import get_cpu_info

# For logging
from logging import getLogger, basicConfig, INFO, DEBUG, ERROR
from sys import stderr


# L'idée c'est de monitorer le temps des opérations de lecture, écriture, mise à jour et suppression
# Avec la classe MongoDB, grâce au monitoring, on peut mesurer le temps des opérations

operation_times		= {}
failed_operations	= {}
system_info			= ""

"""
Collection/Table "Books" :
	id : Identifiant unique (UUID ou Auto-increment pour MySQL, ObjectId pour MongoDB)
	title : Titre du livre (String)
	author : Auteur du livre (String)
	published_date : Date de publication (Date)
	genre : Genre du livre (String)
	copies_sold : Nombre d'exemplaires vendus (Integer)
"""

class CommandLogger(monitoring.CommandListener):
	def started(self, event):
		global operation_times
		# on va initier un tableau de liste de temps selon l'opération
		operation_times = {}
		# On utilisera CommandSucceededEvent pour récupérer le temps de l'opération

	def succeeded(self, event):
		global operation_times
		# On récupère le temps de l'opération
		operation_time = event.duration_micros
		# On récupère le nom de l'opération
		operation_name = event.command_name
  
		# On ajoute le temps de l'opération dans le tableau
		if operation_name not in self.operation_times:
			operation_times[operation_name] = [operation_time]
		else:
			operation_times[operation_name].append(operation_time)

	def failed(self, event):
		#On compte le nombre d'opérations qui ont échoué et on stocke le nom de l'opération, la requête et le message d'erreur
		global failed_operations
		operation_name = event.command_name
		query = event.command
		message = event.failure
		if operation_name not in failed_operations:
			failed_operations[operation_name] = [(query,message)]
		else:
			failed_operations[operation_name].append((query,message))

class MongoDB:
	def __init__(self,using_replica_set: bool=False,using_sharded_cluster:bool = False):
		# Logging
		self.logger = getLogger(__name__)
		basicConfig(level=INFO)
		
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

			mongo_user	= getenv('MONGO_USER',		'root')
			mongo_pass	= getenv('MONGO_PASS',		'root')
			database	= getenv('MONGO_DATABASE',	'database-test')
			collection	= getenv('MONGO_COLLECTION','collection-test')

		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
			raise Exception("MongoDB : Error loading environment variables")

		# Connection to MongoDB
		try:
			if using_replica_set:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											replicaSet=replica_set,
											username=mongo_user,
											password=mongo_pass,
											event_listeners=[CommandLogger()]
										)
			else:
				self.client	= MongoClient(	mongo_host,
											int(mongo_port),
											username=mongo_user,
											password=mongo_pass,
											event_listeners=[CommandLogger()]
										)

			self.db			= self.client[database]
			self.collection = self.db[collection]

		except Exception as e:
			self.logger.error(f"MongoDB.__init__: {e}")
			raise Exception("MongoDB : Error connecting to database")

		# Monitoring
		self.client.set_command_listener(CommandLogger())

	def __del__(self):
		self.client.close()
	
	def create_index(self,field ,unique : bool=False):
		"""
		Create an index on the field
		:param field: the field to index
		"""
		if self.collection.create_index(field,unique=unique) is not None:
			self.logger.debug(f"Index created : {field}")
		else:
			self.logger.error(f"Error creating index : {field}")

	def create_indexes(self,fields:list[IndexModel]):
		"""
		Create indexes on the fields
		:param fields: the fields to index
		"""
		if self.collection.create_indexes(fields) is not None:
			self.logger.debug(f"Indexes created : {fields}")
		else:
			self.logger.error(f"Error creating indexes : {fields}")

	def read(self):
		"""
		Find all documents in the collection
		"""
		for x in self.collection.find():
			self.logger.info(x)

	def read_one(self,query):
		"""
		Find the first document that matches the query
		:param query: the query to find the document
		"""
		x = self.collection.find_one(query)
		self.logger.info(x)

	def create_one(self,data):
		"""
		Insert one document in the collection
		:param data: the document to insert
		"""
		if self.collection.insert_one(data) is not None:
			self.logger.debug(f"Data inserted : {data}")
		else:
			self.logger.error(f"Error inserting data : {data}")

	def update_one(self,query,new_values):
		"""
		Modify the first document that matches the query
		:param query: the query to find the document to update
		:param new_values: the new values to update
		"""
		if self.collection.update_one(query, new_values).modified_count > 0:
			self.logger.debug(f"Data updated : {query} -> {new_values}")
		else:
			self.logger.error(f"No data updated with : {query} -> {new_values}")

	def delete_one(self,query):
		"""
		Delete the first document that matches the query
		:param query: the query to find the document to delete
		"""
		if self.collection.delete_one(query).deleted_count > 0:
			self.logger.debug(f"Data deleted : {query}")
		else:
			self.logger.error(f"No data deleted with : {query}")
	
	# Operations with several documents
	def create_many(self,data):
		"""
		Insert several documents in the collection
		:param data: the documents to insert
		"""
		if self.collection.insert_many(data) is not None:
			self.logger.debug(f"Data inserted : {data}")
		else:
			self.logger.error(f"Error inserting data : {data}")

	def update_many(self,query,new_values):
		"""
		Modify all documents that match the query
		:param query: the query to find the documents to update
		:param new_values: the new values to update
		"""
		if self.collection.update_many(query, new_values).modified_count > 0:
			self.logger.debug(f"Data updated : {query} -> {new_values}")
		else:
			self.logger.error(f"No data updated with : {query} -> {new_values}")

	def delete_many(self,query):
		"""
		Delete all documents that match the query
		:param query: the query to find the documents to delete
		"""
		if self.collection.delete_many(query).deleted_count > 0:
			self.logger.debug(f"Data deleted : {query}")
		else:
			self.logger.error(f"No data deleted with : {query}")
	
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
		self.collection.drop()

	
	def close(self):
		self.client.close()

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
		plt.plot(operation_times[operation], label=operation)
		plt.title('Time of operations')
		plt.xlabel(test_name+ operation )
		plt.ylabel('Time (µs)')
		plt.annotate(system_info, (0,0), (0, -40), xycoords='axes fraction', textcoords='offset points', va='top')
		plt.legend()
		plt.savefig(f"MongoDB_{test_name}_{operation}.png")
		plt.show()


###### Tests de performance ######
	###### Tests avec une seule instance ######

def test_without_index(mongo: MongoDB,plot_name :str):
	global num_records_per_many, generated_file, updated_file
 
	# On récupère les données
	dataset = extract_books_from_file(generated_file)

	### Tests avec données une par une  ###

	## Test d'insertion de données
	for book in dataset:
		mongo.create_one(book)

	## Test de lecture de données sur la collection "Books", en choississant l'id
	for i in range(0,len(dataset)):
		mongo.read_one({"id":i})

	## Test de mise à jour de données
 
	# Chargement des données à modifier
	updated_dataset = extract_updated_books_from_file(updated_file)
	# note : update_dataset contains the original and modified data
	
	for update in updated_dataset:
		mongo.update_one(update["original"],update["modified"])
	
	## Test de suppression de données
	for _,book in updated_dataset:
		mongo.delete_one(book)
	
	# On supprime toutes les données de la collection
	mongo.drop_all()
	
	### Tests avec plusieurs données à la fois  ###
	# On envoie à chaque fois num_records_per_many données
 
	## Test d'insertion de données
	for i in range(0,len(dataset),num_records_per_many):
		mongo.create_many(dataset[i:i+num_records_per_many])

	## Test de lecture de données
	mongo.read()
 
	## Test de mise à jour de données
	for i in range(0,len(updated_dataset),num_records_per_many):
		# On met à jour les données
		mongo.update_many(updated_dataset[i:i+num_records_per_many])

	## Test de suppression de données
	for i in range(0,len(updated_dataset),num_records_per_many):
		# On supprime les données
		mongo.delete_many(updated_dataset[i:i+num_records_per_many])


	# Dessiner les graphiques
	plot_operation_times(plot_name)
	
	# Afficher les opérations qui ont échoué
	print_failed_operations()
 
	# On supprime toutes les données de la collection
	mongo.drop_all()
 
	# On réinitialise les données des opérations
	mongo.clear_operation_data()

def test_with_index(mongo: MongoDB,plot_name :str):
    
	# On définit les index
	indexes = [	IndexModel("id", unique=True), 
				IndexModel("title"), 
				IndexModel("author"), 
				IndexModel("published_date"), 
				IndexModel("genre"), 
				IndexModel("copies_sold")]
	mongo.create_indexes(indexes)
	
	# on va faire les mêmes tests que précédemment
	test_without_index(mongo,plot_name)


	##### Test avec réplication ######



if __name__ == "__main__":

	get_system_info()
	
	try:
		# Test avec une seule instance sans index
		mongo = MongoDB()
		test_without_index(mongo, "single_instance")
		
		# Test avec une seule instance avec index
		test_with_index(mongo,	"single_instance_with_index")
	
		# On fermes les connexions
		mongo.close()
	except Exception as e:
		print(f"Error : {e}")
		print("Test avec instance unique échoué")

	try:
		mongo = MongoDB(using_replica_set=True)
		# Test avec réplication et sans index
		test_without_index(mongo, "replication")
	
		# Test avec réplication et avec index
		test_with_index(mongo, "replication_with_index")
		
		mongo.close()
	except Exception as e:
		print(f"Error : {e}")
		print("Test avec réplication échoué")

	# Test avec sharding
	try:
		mongo = MongoDB()
	
		# Test avec une seule instance avec index
		test_with_index(mongo,	"single_instance_with_index")
	
		# On fermes les connexions
		mongo.close()
	except Exception as e:
		print(f"Error : {e}")
		print("Test avec instance unique échoué")

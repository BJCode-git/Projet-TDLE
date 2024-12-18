import matplotlib.pyplot as plt
import numpy as np
from os import makedirs
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import plotly.graph_objects as go

operation_times = {"test": []}

def generate_data():
	global operation_times
	operation_times["test"] = np.random.normal(2, 100, 10000)

def violin_plot_operation_times(test_type="test", test_name=""):
	"""
	Plot the times of the operations with custom colors for quartiles, median, and mean.
	"""
	global operation_times

	# Créer un dossier pour les graphiques

	# Créer un graphique pour chaque opération
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
		q1 = np.percentile(data, 25)
		q3 = np.percentile(data, 75)
		median = np.median(data)
		mean = np.mean(data)
		
  
		# Ajout du nuage de points 
		x = np.random.normal(loc=1, scale=0.05, size=len(data))  # Ajout de jitter pour éviter l'empilement
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

		# Sauvegarde
		plt.savefig(f"plots/MySQL/{operation}.png")
		plt.show()

		# Réinitialisation du graphe
		plt.clf()

def violin_plot_operation_times2(test_type="test", test_name=""):
	"""
	Affiche un graphique violon avec Plotly pour chaque opération, en ajoutant des lignes pour la médiane, la moyenne, 
	les quartiles, et un nuage de points.
	"""
	global operation_times

	# Créer un graphique pour chaque opération
	for operation, data in operation_times.items():

		# Calcul des statistiques : médiane, moyenne, quartiles
		q1 = np.percentile(data, 25)
		q3 = np.percentile(data, 75)
		median = np.median(data)
		mean = np.mean(data)

		# Création du graphique violon avec Plotly
		fig = go.Figure()

		fig.add_trace(go.Violin(
			y=data,
			box_visible=True,
			meanline_visible=True,
			opacity=0.6,
			name=operation,
			points="all",  # Afficher tous les points
			jitter=0.05,  # Dispersion des points
			pointpos=0,  # Position des points
			
		))
		
		# Mise à jour des axes et du titre
		fig.update_layout(
			title=f"Temps mesuré pour réaliser l'opération: {operation}",
			xaxis_title="Opérations",
			yaxis_title="Temps (µs)",
			template="plotly_white",
			showlegend=True
		)

		# Affichage du graphique
		fig.show()

def violin_plot_with_scatter():
	# Données factices pour tester
	data = [np.random.normal(loc=50, scale=10, size=100) for _ in range(3)]

	# Création du graphe violon
	fig, ax = plt.subplots()
	positions = range(1, len(data) + 1)
	violin_parts = ax.violinplot(data, positions=positions, showmeans=True, showmedians=True)

	# Ajout du nuage de points
	for i, dataset in enumerate(data):
		x = np.random.normal(loc=positions[i], scale=0.05, size=len(dataset))  # Ajout de jitter pour éviter l'empilement
		y = dataset
		ax.scatter(x, y, alpha=0.6, edgecolors="k", label=f"Data {i + 1}" if i == 0 else None)

	# Ajout des labels, titre et légende
	ax.set_title("Graphe violon avec nuage de points")
	ax.set_ylabel("Valeurs")
	ax.set_xlabel("Groupes")
	ax.set_xticks(positions)
	ax.set_xticklabels([f"Groupe {i + 1}" for i in range(len(data))])
	ax.legend(["Nuage de points"], loc="upper right")

	# Affichage
	plt.show()


if __name__ == "__main__":
	generate_data()
	#violin_plot_operation_times2()
	violin_plot_operation_times()
	#violin_plot_with_scatter()
import bibtexparser
import matplotlib.pyplot as plt
# plotting libraries
import networkx as nx
import numpy as np
import pandas as pd
import requests
from bibtexparser.bibdatabase import as_text
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import homogenize_latex_encoding
from pandas.core.frame import DataFrame

# %% Nested Functions

# function extracting needed key values from literature data
def get_literature_keys(literature, member):
    data = pd.DataFrame(
        {
            "paperID": literature["paperId"],
            "authors": [literature["authors"]],
            "year": literature["year"],
            "doi": literature["doi"],
            "title": literature["title"],
            "occurence": 1,
        }
    )

    # add category to paper
    raw_cat = pd.Categorical(
        member, categories=["owned", "new", "recommended"], ordered=False
    )
    data["member"] = raw_cat

    return data


# function extracting needed key values from literature data
def add_literature(all_papers, relationships, newPaper):
    # add relationship between available and referenced paper
    relation = {
        "from": availablePaper.loc[0, "paperID"],
        "to": newPaper.loc[0, "paperID"],
    }
    relationships = relationships.append(relation, ignore_index=True)

    # add referenced paper to all papers
    if any(
        all_papers["paperID"].isin(newPaper["paperID"])
    ):  # IF referenced paper is already saved
        # count occurence of paper up by 1
        all_papers.loc[
            all_papers["paperID"] == newPaper.loc[0, "paperID"], "occurence"
        ] += 1
    else:
        # add referenced paper to all papers
        all_papers = pd.concat([all_papers, newPaper], ignore_index=True)

    return all_papers, relationships


# read data from bib-file
with open("literature.bib") as bibtex_file:
    parser = BibTexParser()
    parser.customization = homogenize_latex_encoding
    bib_database = bibtexparser.load(bibtex_file, parser=parser)


# relationship / connections between papers
relationships = pd.DataFrame({"from": [], "to": []})
# paper information
all_papers = pd.DataFrame(
    {
        "paperID": [],
        "authors": [],
        "year": [],
        "doi": [],
        "title": [],
        "occurence": [],
    }
)

# %% Add Literature Data

counter_connected_papers = 0
# Save author, year, title and doi in dict-variable
for entries in range(len(bib_database.entries)):

    if not "doi" in bib_database.entries[entries]:  # IF entry does not have DOI
        continue

    # get DOI from Literature
    DOI = as_text(bib_database.entries[entries]["doi"])

    # get json-file of literature via DOI
    resp = requests.get("https://api.semanticscholar.org/v1/paper/" + DOI)
    if resp.status_code != 200:
        # This means something went wrong.
        KeyboardInterrupt
        continue

    # giving user status feedback
    print("Paper %i of %i" % (entries, len(bib_database.entries)))

    # another paper is added
    counter_connected_papers += 1

    # get keys of current paper available in bibtex-file
    availablePaper = get_literature_keys(resp.json(), "owned")

    # add available paper to all papers
    if any(
        all_papers["paperID"].isin(availablePaper["paperID"])
    ):  # IF available paper is already saved
        # count occurence of paper up by 1
        all_papers.loc[
            all_papers["paperID"] == availablePaper.loc[0, "paperID"], "occurence"
        ] += 1
        # change membership to owned
        all_papers.loc[
            all_papers["paperID"] == availablePaper.loc[0, "paperID"], "member"
        ] = "owned"
    else:
        # add available paper to all papers
        all_papers = pd.concat([all_papers, availablePaper], ignore_index=True)

    # loop through referenced literature and get key values
    for ref in range(len(resp.json()["references"])):
        referencedPaper = get_literature_keys(resp.json()["references"][ref], "new")
        all_papers, relationships = add_literature(
            all_papers, relationships, referencedPaper
        )

    # loop through cited literature and get key values
    citedLiterature = pd.DataFrame({})
    for ref in range(len(resp.json()["citations"])):
        cited_papers = get_literature_keys(resp.json()["citations"][ref], "new")
        all_papers, relationships = add_literature(
            all_papers, relationships, cited_papers
        )


# %% Clean Data by deleting uninteresting papers (less often cited/ referenced papers)
print(len(all_papers))
# delete all new papers with a number of occurence that lies in the 90%-quantile
delete_papers = all_papers[
    (all_papers["occurence"] <= all_papers["occurence"].quantile(0.95))
    & (all_papers["member"] == "new")
]

# delete papers
idx_delete_papers = np.flatnonzero(all_papers["paperID"].isin(delete_papers["paperID"]))
all_papers = all_papers.drop(idx_delete_papers)

# delete connections in graph
idx_delete_papers = np.flatnonzero(
    relationships["from"].isin(delete_papers["paperID"])
    | relationships["to"].isin(delete_papers["paperID"])
)
relationships = relationships.drop(idx_delete_papers)


# %% identify new papers of possible interest
# interesting papers are identified by their number of occurences. The more often a paper is cited the better is
# must be and the higher its impact on the field can be assumed
new_paper = all_papers[
    (all_papers["occurence"] >= all_papers["occurence"].quantile(0.9))
    & (all_papers["member"] == "new")
]

# change membership to recommended
all_papers.loc[
    all_papers["paperID"].isin(new_paper["paperID"]), "member"
] = "recommended"


# %% User feedback
print(
    "%i of %i papers from bibtex-file were added to graph. \n"
    % (counter_connected_papers, len(bib_database.entries))
)
print(
    "%i of %i extracted papers (cited and referenced) are shown in graph. \n"
    % (len(all_papers), len(all_papers) + len(delete_papers))
)
print("The following %i papers might be of interest: \n" % (len(new_paper)))


papers = []
for i in range(len(new_paper)):
    # extract all author names from each paper
    author_names = [x["name"] for x in new_paper.loc[new_paper.index[i], "authors"]]
    # only use first author as identifier and add year of publication
    papers.append("".join(author_names[0]))

recommended_papers = pd.DataFrame()
recommended_papers["ID"] = papers
recommended_papers["year"] = new_paper["year"].values
recommended_papers["doi"] = new_paper["doi"].values
recommended_papers["title"] = new_paper["title"].values

print(recommended_papers)

# save list of recommended papers
recommended_papers.to_csv("recommended_papers.csv", index=False, float_format="%.2f")

# %% PLOTTING
# Create graph
G = nx.DiGraph()
G.add_nodes_from(all_papers["paperID"])
G.add_edges_from(list(relationships.itertuples(index=False, name=None)))
# G = nx.from_pandas_edgelist(relationships, 'from', 'to', create_using=nx.DiGraph())

# Specify colors
colors = ["darkgray", "dodgerblue", "darkorange"]

# specify labels according to color
# with this the color labels can be different from the node names
ColorLegend = {"new": 0, "owned": 1, "recommended": 2}

# assign colors to nodes
condition = [(all_papers["member"] == "owned"), (all_papers["member"] == "recommended")]
node_colors = np.select(condition, colors[1:], default=colors[0])

# Using a figure to use it as a parameter when calling nx.draw_networkx
f = plt.figure(1)
ax = f.add_subplot(1, 1, 1)
for label in ColorLegend:
    ax.plot([0], [0], color=colors[ColorLegend[label]], label=label)


# Set node size by number of occurences in a variable manner so that paper with maximum
# number of occurence has always the same size independently of its number of occurence
maxValue = all_papers["occurence"].max()
minValue = all_papers["occurence"].min()
sizingFactor = 100 / (maxValue - minValue)
nodeSize = np.ceil((all_papers["occurence"] - minValue + 1) * sizingFactor).tolist()

# Draw graph
position = nx.spring_layout(G)
nx.draw(
    G,
    pos=position,
    width=0.5,
    node_size=nodeSize,
    node_color=node_colors,
    edge_color="gray",
    cmap=colors,
)


# identfiy papers in plot by name of first author and year of publication
paper_identifier = []
for i in range(len(all_papers)):
    # extract all author names from each paper
    author_names = [x["name"] for x in all_papers.loc[all_papers.index[i], "authors"]]
    # only use first author as identifier and add year of publication
    paper_identifier.append(
        "".join(
            author_names[0]
            + "\n"
            + str(int(all_papers.loc[all_papers.index[i], "year"]))
        )
    )

# set node names only for recommended papers
node_labels = np.where(all_papers["member"] == "recommended", paper_identifier, "")
labels = dict(zip(all_papers["paperID"], node_labels))

# Now only add labels to the nodes you require
nx.draw_networkx_labels(G, position, labels, font_size=12)

# plot legend
plt.legend()

# save plot
plt.savefig("paper connections.png")

# show plot
plt.show()
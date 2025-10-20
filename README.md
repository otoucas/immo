## `README.md`

Application Streamlit pour interroger les données open data ADEME (DPE/GES) et afficher les résultats (adresse, DPE, GES, surface) sur une **carte** et un **tableau** en permanence. Intégration d’indices DVF (à la même adresse) dans la fiche (popup) de chaque résultat.


## Environnements / configuration

Les URLs d’API sont centralisées dans `config.py`. Adaptez si nécessaire les slugs/URLs des datasets.
> Remarque : certains producteurs exposent les données via Data Fair avec des endpoints de type `/datasets/<slug>/lines`. Si l’URL précise change, ne modifier que `config.py`.

#!/bin/bash

# Abrufen der neuesten Änderungen vom Remote-Repository
git fetch --all

# Auflisten aller lokalen Branches, damit der Benutzer einen zum Mergen auswählen kann
echo "Verfügbare lokale Branches:"
git branch

read -p "Welchen Branch möchten Sie in main mergen? " branch_name

# Überprüfen, ob der Branch existiert
if ! git show-ref --verify --quiet refs/heads/$branch_name; then
    echo "Fehler: Branch '$branch_name' nicht gefunden."
    exit 1
fi

# Auschecken des main-Branches
git checkout main

# Mergen des ausgewählten Branches in den main-Branch
git merge $branch_name

# Überprüfen, ob der Merge erfolgreich war
if [ $? -ne 0 ]; then
    echo "Fehler beim Mergen. Bitte beheben Sie die Konflikte und führen Sie den Merge manuell durch."
    exit 1
fi

# Pushen des main-Branches zum Remote-Repository
git push origin main

# Überprüfen, ob der Push erfolgreich war
if [ $? -ne 0 ]; then
    echo "Fehler beim Pushen zu main."
    exit 1
fi

# Löschen des lokalen Branches nach dem erfolgreichen Mergen
read -p "Möchten Sie den Branch '$branch_name' lokal löschen? (j/n) " delete_branch
if [ "$delete_branch" == "j" ]; then
    git branch -d $branch_name
    echo "Branch '$branch_name' wurde lokal gelöscht."
fi

echo "Merge und Push erfolgreich abgeschlossen."

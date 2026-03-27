#!/bin/bash

# Container stoppen und entfernen
sudo docker stop postgresql
sudo docker rm postgresql
sudo docker stop litellm
sudo docker rm litellm

# Volumes entfernen
sudo docker volume rm beyond-the-loop_postgresql
sudo docker volume rm beyond-the-loop_litellm
sudo docker volume rm beyond-the-loop_beyond-the-loop

# Optional: Zeige verbleibende Volumes
echo "Verbleibende Volumes:"
sudo docker volume ls
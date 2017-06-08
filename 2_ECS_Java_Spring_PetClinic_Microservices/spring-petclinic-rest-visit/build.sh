#!/bin/bash

result=${PWD##*/}
aws ecr create-repository --repository-name ${result}
mvn package docker:build -DpushImage -Dmaven.test.skip=true -X
elbv2 create-target-group --name ${result} --port 8080 --vpc-id vpc-ee5f6d89 --protocol HTTP
FROM frolvlad/alpine-oraclejdk8:slim
VOLUME /tmp
ADD spring-petclinic-rest-vet-1.7.jar app.jar
RUN sh -c 'touch /app.jar'
RUN apk add --no-cache py-pip python jq && pip install awscli
ENTRYPOINT java -Dspring.datasource.password=$(aws ssm get-parameters --name $DBPasswordSSMKey --with-decryption --query Parameters[0].Value --region $AWS_Region|sed -e 's/\"//g') -Djava.security.egd=file:/dev/./urandom -jar app.jar

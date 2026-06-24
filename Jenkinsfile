pipeline {
    agent any

    parameters {
        choice(
            name: 'ACTION',
            choices: ['BUILD_AND_DEPLOY', 'BUILD_ONLY', 'DEPLOY_ONLY'],
            description: 'Choose pipeline action'
        )

        string(
            name: 'DEPLOY_IMAGE_TAG',
            defaultValue: '',
            description: 'Required only for DEPLOY_ONLY. Example: 1.0.25 or latest'
        )
    }

    environment {
        SONAR_HOST_URL = 'https://sonarcloud.io'
        SONAR_ORG = 'siddhartha-raja'
        SONAR_PROJECT_KEY = 'Java-Test'
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Code checked out by Jenkins SCM'
                sh 'ls -la'
            }
        }

        stage('Load Config') {
            steps {
                script {
                    def props = readProperties file: 'ci-config.properties'

                    env.APP_NAME = props['APP_NAME']

                    env.GROUP_ID = props['GROUP_ID']
                    env.ARTIFACT_ID = props['ARTIFACT_ID']

                    env.NEXUS_URL = props['NEXUS_URL']
                    env.NEXUS_REPO = props['NEXUS_REPO']

                    env.AWS_REGION = props['AWS_REGION']
                    env.ECR_REPO = props['ECR_REPO']

                    env.K8S_DEPLOYMENT = props['K8S_DEPLOYMENT']
                    env.K8S_SERVICE = props['K8S_SERVICE']

                    if (props['APP_VERSION'] == 'AUTO') {
                        env.APP_VERSION = "1.0.${env.BUILD_NUMBER}"
                    } else {
                        env.APP_VERSION = props['APP_VERSION']
                    }

                    if (props['DOCKER_IMAGE_TAG'] == 'AUTO') {
                        env.DOCKER_IMAGE_TAG = env.APP_VERSION
                    } else {
                        env.DOCKER_IMAGE_TAG = props['DOCKER_IMAGE_TAG']
                    }

                    if (params.ACTION == 'DEPLOY_ONLY') {
                        if (params.DEPLOY_IMAGE_TAG == null || params.DEPLOY_IMAGE_TAG.trim() == '') {
                            error "DEPLOY_IMAGE_TAG is required when ACTION=DEPLOY_ONLY"
                        }

                        env.DOCKER_IMAGE_TAG = params.DEPLOY_IMAGE_TAG.trim()
                        env.APP_VERSION = params.DEPLOY_IMAGE_TAG.trim()
                    }

                    echo "ACTION: ${params.ACTION}"
                    echo "APP_VERSION: ${env.APP_VERSION}"
                    echo "DOCKER_IMAGE_TAG: ${env.DOCKER_IMAGE_TAG}"
                }
            }
        }

        stage('Maven Build') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh 'mvn clean compile'
            }
        }

        stage('Unit Test') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh 'mvn test'
            }
        }

        stage('SonarCloud Scan') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    sh """
                    mvn sonar:sonar \
                      -Dsonar.host.url=${SONAR_HOST_URL} \
                      -Dsonar.organization=${SONAR_ORG} \
                      -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
                      -Dsonar.login=$SONAR_TOKEN
                    """
                }
            }
        }

        stage('Set Unique Maven Version') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh """
                mvn versions:set -DnewVersion=${APP_VERSION}
                grep '<version>' pom.xml | head
                """
            }
        }

        stage('Build and Push JAR to Nexus') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh """
                mvn clean deploy -DskipTests
                """
            }
        }

        stage('Download JAR from Nexus') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'nexus-creds', usernameVariable: 'NEXUS_USER', passwordVariable: 'NEXUS_PASS')]) {
                    sh """
                    GROUP_PATH=\$(echo ${GROUP_ID} | tr '.' '/')

                    JAR_URL="${NEXUS_URL}/repository/${NEXUS_REPO}/\${GROUP_PATH}/${ARTIFACT_ID}/${APP_VERSION}/${ARTIFACT_ID}-${APP_VERSION}.jar"

                    echo "Downloading JAR from Nexus:"
                    echo "\${JAR_URL}"

                    rm -f app.jar

                    curl -f -u "$NEXUS_USER:$NEXUS_PASS" \
                      -o app.jar \
                      "\${JAR_URL}"

                    ls -lh app.jar
                    """
                }
            }
        }

        stage('Get AWS Account ID') {
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-creds']]) {
                    script {
                        env.AWS_ACCOUNT_ID = sh(
                            script: "aws sts get-caller-identity --query Account --output text",
                            returnStdout: true
                        ).trim()

                        env.ECR_URI = "${env.AWS_ACCOUNT_ID}.dkr.ecr.${env.AWS_REGION}.amazonaws.com/${env.ECR_REPO}"

                        echo "AWS Account ID: ${env.AWS_ACCOUNT_ID}"
                        echo "ECR URI: ${env.ECR_URI}"
                    }
                }
            }
        }

        stage('Login to AWS ECR') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-creds']]) {
                    sh """
                    aws ecr get-login-password --region ${AWS_REGION} | \
                    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                    """
                }
            }
        }

        stage('Docker Build from Nexus JAR') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh """
                docker build -t ${ECR_REPO}:${DOCKER_IMAGE_TAG} .

                docker tag ${ECR_REPO}:${DOCKER_IMAGE_TAG} ${ECR_URI}:${DOCKER_IMAGE_TAG}
                docker tag ${ECR_REPO}:${DOCKER_IMAGE_TAG} ${ECR_URI}:latest
                """
            }
        }

        stage('Push Docker Image to ECR') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'BUILD_ONLY' }
                }
            }
            steps {
                sh """
                docker push ${ECR_URI}:${DOCKER_IMAGE_TAG}
                docker push ${ECR_URI}:latest
                """
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                anyOf {
                    expression { params.ACTION == 'BUILD_AND_DEPLOY' }
                    expression { params.ACTION == 'DEPLOY_ONLY' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    echo "Deploying image:"
                    echo "${ECR_URI}:${DOCKER_IMAGE_TAG}"

                    cp k8s/deployment.yaml k8s/deployment-generated.yaml

                    sed -i 's|IMAGE_NAME|${ECR_URI}:${DOCKER_IMAGE_TAG}|g' k8s/deployment-generated.yaml

                    kubectl apply -f k8s/deployment-generated.yaml
                    kubectl apply -f k8s/service.yaml

                    kubectl rollout status deployment/${K8S_DEPLOYMENT}
                    kubectl get pods -o wide
                    kubectl get svc ${K8S_SERVICE}
                    """
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline successful."
            echo "Action: ${params.ACTION}"
            echo "Image used: ${ECR_URI}:${DOCKER_IMAGE_TAG}"

            script {
                if (params.ACTION != 'DEPLOY_ONLY') {
                    echo "JAR pushed to Nexus:"
                    echo "${NEXUS_URL}/repository/${NEXUS_REPO}/${GROUP_ID}/${ARTIFACT_ID}/${APP_VERSION}"
                    echo "Docker image pushed:"
                    echo "${ECR_URI}:${DOCKER_IMAGE_TAG}"
                }

                if (params.ACTION != 'BUILD_ONLY') {
                    echo "Application deployed to Kubernetes."
                }
            }
        }

        failure {
            echo 'Pipeline failed. Check console logs.'
        }
    }
}

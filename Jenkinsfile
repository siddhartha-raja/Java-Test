pipeline {
    agent any

    environment {
        SONAR_HOST_URL = 'https://sonarcloud.io'
        SONAR_ORG = 'siddhartha-raja'
        SONAR_PROJECT_KEY = 'Java-Test'

        AWS_REGION = 'us-east-1'
        ECR_REPO = 'java-test'
        IMAGE_TAG = "${BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Code checked out by Jenkins SCM'
                sh 'ls -la'
            }
        }

        stage('Maven Build') {
            steps {
                sh 'mvn clean compile'
            }
        }

        stage('Unit Test') {
            steps {
                sh 'mvn test'
            }
        }

        stage('SonarCloud Scan') {
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

        stage('Package') {
            steps {
                sh 'mvn package -DskipTests'
            }
        }

        stage('Upload Artifact to Nexus') {
            steps {
                sh 'mvn deploy -DskipTests'
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
            steps {
                withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-creds']]) {
                    sh """
                    aws ecr get-login-password --region ${AWS_REGION} | \
                    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                    """
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh """
                docker build -t ${ECR_REPO}:${IMAGE_TAG} .
                docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}
                docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URI}:latest
                """
            }
        }

        stage('Push Image to ECR') {
            steps {
                sh """
                docker push ${ECR_URI}:${IMAGE_TAG}
                docker push ${ECR_URI}:latest
                """
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    cp k8s/deployment.yaml k8s/deployment-generated.yaml

                    sed -i 's|IMAGE_NAME|${ECR_URI}:${IMAGE_TAG}|g' k8s/deployment-generated.yaml

                    kubectl apply -f k8s/deployment-generated.yaml
                    kubectl apply -f k8s/service.yaml

                    kubectl rollout status deployment/java-test
                    kubectl get pods -o wide
                    kubectl get svc java-test-service
                    """
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline successful."
            echo "Docker image pushed: ${ECR_URI}:${IMAGE_TAG}"
        }

        failure {
            echo 'Pipeline failed. Check console logs.'
        }
    }
}

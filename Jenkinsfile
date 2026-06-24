pipeline {
    agent {
        label 'docker-agent'
    }

    parameters {
        choice(
            name: 'ACTION',
            choices: ['BUILD_ONLY', 'BUILD_AND_DEPLOY', 'DEPLOY_ONLY'],
            description: 'Choose pipeline action'
        )

        string(
            name: 'DEPLOY_IMAGE_TAG',
            defaultValue: '',
            description: 'Required only for DEPLOY_ONLY. Example: 1.0.25 or latest'
        )

        booleanParam(
            name: 'RUN_REGRESSION',
            defaultValue: false,
            description: 'Run regression tests after deployment'
        )

        booleanParam(
            name: 'RUN_LOAD_TEST',
            defaultValue: false,
            description: 'Run load test after deployment'
        )

        booleanParam(
            name: 'RUN_STRESS_TEST',
            defaultValue: false,
            description: 'Run stress test after deployment'
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

                    env.APP_PUBLIC_IP = props['APP_PUBLIC_IP'] ?: '98.81.5.201'
                    env.SMOKE_PATH = props['SMOKE_PATH'] ?: '/'
                    env.REGRESSION_PATHS = props['REGRESSION_PATHS'] ?: '/'

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

                    if (params.ACTION?.trim() == 'DEPLOY_ONLY') {
                        if (params.DEPLOY_IMAGE_TAG == null || params.DEPLOY_IMAGE_TAG.trim() == '') {
                            error "DEPLOY_IMAGE_TAG is required when ACTION=DEPLOY_ONLY"
                        }

                        env.DOCKER_IMAGE_TAG = params.DEPLOY_IMAGE_TAG.trim()
                        env.APP_VERSION = params.DEPLOY_IMAGE_TAG.trim()
                    }

                    echo "ACTION: ${params.ACTION}"
                    echo "APP_VERSION: ${env.APP_VERSION}"
                    echo "DOCKER_IMAGE_TAG: ${env.DOCKER_IMAGE_TAG}"
                    echo "APP_PUBLIC_IP: ${env.APP_PUBLIC_IP}"
                    echo "SMOKE_PATH: ${env.SMOKE_PATH}"
                    echo "REGRESSION_PATHS: ${env.REGRESSION_PATHS}"
                }
            }
        }

        stage('Maven Build') {
            when {
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
                }
            }
            steps {
                sh 'mvn clean compile'
            }
        }

        stage('Unit Test') {
            when {
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
                }
            }
            steps {
                sh 'mvn test'
            }
        }

        stage('Integration Test') {
            when {
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
                }
            }
            steps {
                sh '''
                echo "Running integration tests..."

                if find src/test/java -name '*IT.java' -o -name '*IntegrationTest.java' | grep -q .; then
                    mvn test -Dtest='*IT,*IntegrationTest'
                else
                    echo "No integration test classes found. Skipping integration test."
                fi
                '''
            }
        }

        stage('SonarCloud Scan') {
            when {
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_ONLY' || params.ACTION == 'BUILD_AND_DEPLOY'
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
                expression {
                    return params.ACTION == 'BUILD_AND_DEPLOY' || params.ACTION == 'DEPLOY_ONLY'
                }
            }
            steps {
                withCredentials([
                    file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG'),
                    [$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-creds']
                ]) {
                    sh """
                    echo "Deploying image:"
                    echo "${ECR_URI}:${DOCKER_IMAGE_TAG}"

                    echo "Refreshing ECR pull secret..."
                    kubectl delete secret ecr-secret --ignore-not-found

                    kubectl create secret docker-registry ecr-secret \
                      --docker-server=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com \
                      --docker-username=AWS \
                      --docker-password="\$(aws ecr get-login-password --region ${AWS_REGION})"

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

        stage('Smoke Test Live App') {
            when {
                expression {
                    return params.ACTION == 'BUILD_AND_DEPLOY' || params.ACTION == 'DEPLOY_ONLY'
                }
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    echo "Running smoke test..."

                    SERVICE_PORT=\$(kubectl get svc ${K8S_SERVICE} -o jsonpath='{.spec.ports[0].nodePort}')
                    APP_URL="http://${APP_PUBLIC_IP}:\${SERVICE_PORT}${SMOKE_PATH}"

                    echo "Smoke test URL: \${APP_URL}"

                    curl -f --connect-timeout 5 --max-time 20 "\${APP_URL}"

                    echo "Smoke test passed."
                    """
                }
            }
        }

        stage('Regression Test Live App') {
            when {
                allOf {
                    expression { return params.RUN_REGRESSION == true }
                    expression { return params.ACTION == 'BUILD_AND_DEPLOY' || params.ACTION == 'DEPLOY_ONLY' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    echo "Running regression tests..."

                    SERVICE_PORT=\$(kubectl get svc ${K8S_SERVICE} -o jsonpath='{.spec.ports[0].nodePort}')

                    echo "${REGRESSION_PATHS}" | tr ',' '\\n' | while read path
                    do
                        URL="http://${APP_PUBLIC_IP}:\${SERVICE_PORT}\${path}"
                        echo "Testing: \${URL}"
                        curl -f --connect-timeout 5 --max-time 20 "\${URL}"
                    done

                    echo "Regression tests passed."
                    """
                }
            }
        }

        stage('Load Test Live App') {
            when {
                allOf {
                    expression { return params.RUN_LOAD_TEST == true }
                    expression { return params.ACTION == 'BUILD_AND_DEPLOY' || params.ACTION == 'DEPLOY_ONLY' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    echo "Running load test..."

                    SERVICE_PORT=\$(kubectl get svc ${K8S_SERVICE} -o jsonpath='{.spec.ports[0].nodePort}')
                    APP_URL="http://${APP_PUBLIC_IP}:\${SERVICE_PORT}${SMOKE_PATH}"

                    echo "Load test URL: \${APP_URL}"
                    echo "Sending 100 requests with 10 parallel workers..."

                    rm -f load-test-results.txt

                    seq 1 100 | xargs -n1 -P10 -I{} sh -c 'curl -s -o /dev/null -w "%{http_code}\\n" "'"\${APP_URL}"'"' | tee load-test-results.txt

                    TOTAL=\$(cat load-test-results.txt | wc -l)
                    SUCCESS=\$(grep -E "200|301|302" load-test-results.txt | wc -l)
                    FAILED=\$(grep -v -E "200|301|302" load-test-results.txt | wc -l)

                    echo "Total requests: \${TOTAL}"
                    echo "Successful requests: \${SUCCESS}"
                    echo "Failed requests: \${FAILED}"

                    if [ "\${FAILED}" -gt 0 ]; then
                        echo "Load test failed."
                        exit 1
                    fi

                    echo "Load test passed."
                    """
                }
            }
        }

        stage('Stress Test Live App') {
            when {
                allOf {
                    expression { return params.RUN_STRESS_TEST == true }
                    expression { return params.ACTION == 'BUILD_AND_DEPLOY' || params.ACTION == 'DEPLOY_ONLY' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh """
                    echo "Running stress test..."

                    SERVICE_PORT=\$(kubectl get svc ${K8S_SERVICE} -o jsonpath='{.spec.ports[0].nodePort}')
                    APP_URL="http://${APP_PUBLIC_IP}:\${SERVICE_PORT}${SMOKE_PATH}"

                    echo "Stress test URL: \${APP_URL}"
                    echo "Sending 500 requests with 50 parallel workers..."

                    rm -f stress-test-results.txt

                    seq 1 500 | xargs -n1 -P50 -I{} sh -c 'curl -s -o /dev/null -w "%{http_code}\\n" "'"\${APP_URL}"'"' | tee stress-test-results.txt

                    TOTAL=\$(cat stress-test-results.txt | wc -l)
                    SUCCESS=\$(grep -E "200|301|302" stress-test-results.txt | wc -l)
                    FAILED=\$(grep -v -E "200|301|302" stress-test-results.txt | wc -l)

                    echo "Total requests: \${TOTAL}"
                    echo "Successful requests: \${SUCCESS}"
                    echo "Failed requests: \${FAILED}"

                    if [ "\${FAILED}" -gt 10 ]; then
                        echo "Stress test failed. More than 10 failed requests."
                        exit 1
                    fi

                    echo "Stress test passed."
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

                if (params.RUN_REGRESSION == true) {
                    echo "Regression testing completed."
                }

                if (params.RUN_LOAD_TEST == true) {
                    echo "Load testing completed."
                }

                if (params.RUN_STRESS_TEST == true) {
                    echo "Stress testing completed."
                }
            }
        }

        failure {
            echo 'Pipeline failed. Check console logs.'
        }
    }
}

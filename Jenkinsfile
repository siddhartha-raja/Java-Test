pipeline {
    agent any

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

        stage('Package') {
            steps {
                sh 'mvn package -DskipTests'
            }
        }
    }

    post {
        success {
            echo 'Build successful'
        }
        failure {
            echo 'Build failed'
        }
    }
}

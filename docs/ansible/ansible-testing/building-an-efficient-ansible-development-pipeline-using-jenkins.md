
# Building an Efficient Ansible Development Pipeline Using Jenkins

## Step 1 — Create the Jenkins pipeline

This pipeline is designed to efficiently test both Ansible roles and playbooks.

```groovy
#!/usr/bin/env groovy

/* Start Pipeline */
pipeline {
    /* Define variables in Pipeline */
    environment {
        GIT_URL = 'YOUR_GIT_REPOSITORY'
        GIT_BRANCH = 'main'
        GIT_CREDENTIALS = 'JENKINS_CREDENTIAL_ID'
        SKIP_DESTROY = 'true'
    }
    /* End Define variables in Pipeline */

    agent any

    /* Start Pipeline Stages */
    stages {
        /* Clean up the Workspace */
        stage("CleanWorkspace") {
            steps {
                cleanWs(
                    notFailBuild: true,
                    deleteDirs: true,
                )
            }
        }
        /* End Clean up the Workspace */

        /* Pull Ansible code from GIT */
        stage('Checkout') {
            steps {
                script {
                    properties([pipelineTriggers([pollSCM('* * * * *')])])
                }
                checkout([$class: 'GitSCM',
                          branches: [[name: "${GIT_BRANCH}"]],
                          doGenerateSubmoduleConfigurations: false,
                          extensions: [],
                          submoduleCfg: [],
                          userRemoteConfigs: [[credentialsId: "${GIT_CREDENTIALS}", url: "${GIT_URL}"]]
                ])
            }
            post {
                success {
                    echo 'GIT checkout success!'
                }
                unstable {
                    echo 'I am unstable :/'
                }
                failure {
                    echo 'GIT checkout failed :('
                }
               
            }
        }
        /* End Pull Ansible code from GIT */
       /* Check YAML file */
       stage('Standardize YAML file') {
            steps {
                dir("${WORKSPACE}") {
                    sh "yamllint ."
                }
            }
        }
        /* End Check YAML file */


        /* Coding standards/best practices - Linting Ansible code */
        stage('Code standards') {
            steps {
                dir("${WORKSPACE}") {
                    sh "cd ${WORKSPACE} && ansible-lint -c ~/.ansible-lint"
                }
            }
        }
        /* End Coding standards/best practices - Linting Ansible code */

        /* Ansible integration tests */
       stage('Integration tests') {
            steps {
                dir("${WORKSPACE}") {
                    sh "molecule converge"
                }
            }
        }
        /* End Ansible integration tests */

        /* Destroy integration tests */
        stage('Destroy integration infrastructure') {
            when {
        environment name: 'SKIP_DESTROY', value: 'true'
    }
            steps {
                dir("${WORKSPACE}") {
                    sh "molecule destroy"
                }
            }
        }
        /* End Destroy integration tests */
    } // Closing bracket for stages section

    /* End Pipeline Stages */
}
/* End Pipeline */
```

## Short Description:

When the Jenkins pipeline is triggered, it performs the following steps:

1.  CleanWorkspace: Clears the workspace by emptying the folder.
2.  Checkout: Retrieves code from the GIT repository.
3.  YAML Linting: Performs linting on YAML files.
4.  Code Standards: Checks Ansible code using ansible-lint.
5.  Integration Tests: Deploys a test environment using Molecule with Docker.
6.  Destroy Integration Infrastructure: Destroys the test environment.

## Step 2 — Integrating GIT with Jenkins

By creating a webhook, pushing code to GIT triggers the Jenkins pipeline to execute all the mentioned steps automatically.

## Conclusion:

Implementing this automation saves a substantial amount of time compared to manual execution of the outlined steps.

## Reference

- https://medium.com/@alexandru.raul/building-an-efficient-ansible-development-pipeline-using-jenkins-8830a0a19de0
- 
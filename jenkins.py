#!/usr/bin/env python3
"""Python script to lauch jenkins job.
   This script only support user TOKEN as the password and not the actual user password
"""
import requests
import re
import sys
import json
import time
import os
import argparse
import logging

QUEUE_POLL_INTERVAL = 2
JOB_POLL_INTERVAL = 20
OVERALL_TIMEOUT = 3600  # 1 hour


def main(arguments):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('job_name', help="Name of the job to launch", type=str)
    parser.add_argument('-u',
                        '--user',
                        help="Username to authenticate to Jenkins",
                        type=str)
    parser.add_argument('-pwd',
                        '--password',
                        help="Token or password to authenticate to Jenkins",
                        type=str)
    parser.add_argument(
        '-j',
        '--jenkins_url',
        help="Jenkins full URL. example : http://localhost:8080",
        type=str)
    parser.add_argument(
        '--tls-verify',
        default = True,
        help="Enable or disable TLS verification for HTTPS connections",
        type=bool)
    parser.add_argument(
        '-p',
        '--param',
        help=
        "Parameter to pass to jenkins job. Example : -p param1=value1 param2=value2",
        default=[],
        nargs='+')

    # get args and set logs
    args = parser.parse_args(arguments)

    logging.basicConfig(
        level=logging.DEBUG,
        format=
        '%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    job_name = args.job_name
    logging.info('Launching Jenkins Job')
    # Launch job
    auth = (args.user, args.password)
    if args.param:
        start_build_url = '{}/job/{}/buildWithParameters?{}'.format(
            args.jenkins_url, job_name, "&".join(args.param))
    else:
        start_build_url = '{}/job/{}/build'.format(args.jenkins_url, job_name)

    r = requests.post(start_build_url, auth=auth, verify=args.tls_verify)

    if r.status_code // 200 == 1:
        logging.info('Job "{}" was launched successfully'.format(job_name))
    else:
        logging.error(
            'An error has occured while lanching the job "{}"'.format(
                job_name))
        exit(2)
    # Check JOB in Jenkins Queue
    job_info_url = r.headers["Location"] + 'api/json'

    elasped_time = 0
    logging.info('{} Job {} added to queue: {}'.format(time.ctime(), job_name,
                                                       job_info_url))
    while True:
        l = requests.get(job_info_url, auth=auth, verify=args.tls_verify)
        jqe = l.json()
        task = jqe['task']['name']
        try:
            job_id = jqe['executable']['number']
            break
        except:
            logging.info("no job ID yet for build: {}".format(task))
            time.sleep(QUEUE_POLL_INTERVAL)
            elasped_time += QUEUE_POLL_INTERVAL

        if (elasped_time % (QUEUE_POLL_INTERVAL * 10)) == 0:
            logging.info("{}: Job {} not started yet from queue".format(
                time.ctime(), job_name))

    ### Check Job status
    job_id_url = jqe['executable']["url"][jqe['executable']["url"].find("/job"
                                                                        ):]
    job_url = args.jenkins_url + job_id_url + 'api/json'
    start_epoch = int(time.time())
    while True:
        logging.info("{}: Job started URL: {}".format(time.ctime(), job_url))
        j = requests.get(job_url, auth=auth, verify=args.tls_verify)
        jje = j.json()
        result = jje['result']
        if result == 'SUCCESS':
            # Do success steps
            logging.info("{}: Job: {} Status: {}".format(
                time.ctime(), job_name, result))
            break
        elif result == 'FAILURE':
            # Do failure steps
            logging.info("{}: Job: {} Status: {}".format(
                time.ctime(), job_name, result))
            break
        elif result == 'ABORTED':
            # Do aborted steps
            logging.info("{}: Job: {} Status: {}".format(
                time.ctime(), job_name, result))
            break
        else:
            logging.info(
                "{}: Job: {} Status: {}. Polling again in {} secs".format(
                    time.ctime(), job_name, result, JOB_POLL_INTERVAL))

        cur_epoch = int(time.time())
        if (cur_epoch - start_epoch) > OVERALL_TIMEOUT:
            logging.info("{}: No status before timeout of {} secs".format(
                OVERALL_TIMEOUT))
            sys.exit(1)

        time.sleep(JOB_POLL_INTERVAL)
    return (0)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

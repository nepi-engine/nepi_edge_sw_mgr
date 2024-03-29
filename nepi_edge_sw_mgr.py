#!/usr/bin/env python3
#
# Copyright (c) 2024 Numurus, LLC <https://www.numurus.com>.
#
# This file is part of nepi-engine
# (see https://github.com/nepi-engine).
#
# License: 3-clause BSD, see https://opensource.org/licenses/BSD-3-Clause
#

import os
import yaml
import shutil
import datetime
import argparse

class NepiEdgeSwMgr:
    # Class Constants
    INSTALL_FILENAME = 'install.yaml'
    UNINSTALL_FILENAME = 'uninstall.yaml'

    def __init__(self):
        self.results_list = []
        self.dry_run = False
        self.results_path = None

    def process_sw_folder(self, sw_folder_path, results_path='.', dry_run=False):
        self.results_path=results_path
        self.dry_run = dry_run
        self.results_list.clear()
        did_something = False
        self.results_list.append(
            {'device_timestamp':datetime.datetime.now().isoformat('T'),
             'input_folder':sw_folder_path,
             'output_folder':self.results_path,
             'dry_run': self.dry_run})
        for (root,dirs,files) in os.walk(sw_folder_path, topdown=True):
            # A directory called Prenstall should be processed first if it exists... we reorder dirs in place to make sure that happens.
            if 'Preinstall' in dirs:
                dirs.insert(0, dirs.pop(dirs.index('Preinstall'))) # Clever way to push it to the front

            for f in files:
                if (f != self.INSTALL_FILENAME and f != self.UNINSTALL_FILENAME): # Skip everything but install/uninstall.yaml
                    continue
                f_path = os.path.join(root, f)
                if (self.process_component(f_path) is True) and (self.dry_run is False):
                    did_something = True


        # Dump the results
        #print(self.results_list)

        # Only generate a file if we actually did something -- file existence is used as an indicator downstream, so delete it
        # if there is nothing to report
        output_file = os.path.join(self.results_path, 'sw_update_status.yaml')
        if (True == os.path.isfile(output_file)):
            os.remove(output_file)
        if did_something is True:
            with open(output_file, 'w') as f:
                yaml.dump_all(self.results_list, f, sort_keys=False)

    def process_component(self, f_path):
        some_instruction_executed = False
        with open(f_path, 'r') as f:
            #print(component_results_dict)
            yaml_docs = list(yaml.load_all(f, Loader=yaml.FullLoader))
            if not yaml_docs: # Empty document for some reason -- just skip it
                #print('Empty Component: ' + f_path + ' (' + str(doc_count) + ')')
                return False # Indicate nothing executed

            # Create a new results dictionary for this component.
            self.results_list.append({'path':os.path.dirname(f_path)})
            component_results_dict = self.results_list[-1]

            #print('Non-empty Component: ' + f_path + ' (' + str(doc_count) + ')')
            is_header_doc = True
            for doc in yaml_docs:
                last_instruction_success = True
                instruction_seq_results_list = []

                if (is_header_doc):
                    # Process the 'header' document by copying some of its fields to the results for this component
                    header_doc = doc
                    if 'component_name' in doc and 'version' in doc:
                        component_results_dict['component_name'] = header_doc['component_name']
                    else:
                        component_results_dict['component_name'] = 'NOT SET'
                        component_results_dict['results'] = ({'result':'failure', 'error_msg':'Invalid Component Name... component aborted'})
                        return
                    if 'version' in header_doc:
                        component_results_dict['version'] = header_doc['version']
                    else:
                        component_results_dict['version'] = 'NOT SET'
                        component_results_dict['results'] = ({'result':'failure', 'error_msg':'Invalid Version... component aborted'})
                        return
                    is_header_doc = False
                else:
                    if 'instruction_sequence' in doc:
                        seq = doc['instruction_sequence']
                        for instruction_dict in seq:
                            for instruction in instruction_dict:
                                instruction_results_dict = {}
                                instruction_results_dict['type'] = instruction
                                # Process instructions as long as the previous instruction was successful
                                if (True == last_instruction_success):
                                    some_instruction_executed = True
                                    last_instruction_success = self.process_instruction(instruction, instruction_dict[instruction], instruction_results_dict, os.path.dirname(f_path))
                                    instruction_results_dict['result'] = 'success' if True == last_instruction_success else 'failure'
                                else:
                                    instruction_results_dict['result'] = 'aborted'
                                instruction_seq_results_list.append(instruction_results_dict)

                if instruction_seq_results_list:
                    component_results_dict['results'] = instruction_seq_results_list
        return some_instruction_executed # Indicate something was actually done

    def process_instruction(self, instruction, parameters, results_dict, working_dir):
        # Basically just a big jump table
        if (instruction == 'dependency_check'):
            return self.do_dependency_check(parameters, results_dict)
        elif (instruction == 'file_install'):
            return self.do_file_install(parameters, results_dict, working_dir)
        elif (instruction == 'file_delete'):
            return self.do_file_delete(parameters, results_dict)
        elif (instruction == 'directory_delete'):
            return self.do_directory_delete(parameters, results_dict)
        else:
            results_dict['error_msg'] = 'Unknown instruction: ' + instruction
            return False

    def do_dependency_check(self, dependency_list, results_dict):
        for dep in dependency_list:
            #if (False == self.dry_run):
            if (True): # Just for generating rich test output, don't commit
                if (False == os.path.isfile(dep)):
                    results_dict['error_msg'] = 'No such file: ' + dep
                    return False
        return True

    def do_file_install(self, parameters, results_dict, working_dir):
        # First, make sure we have all required parameters
        if ('source' not in parameters):
            results_dict['error_msg'] = 'File install instruction must provide a source'
            return False
        if ('destination' not in parameters):
            results_dict['error_msg'] = 'File install instruction must provide a destination'
            return False

        source_file = os.path.join(working_dir, parameters['source'])
        destination_file = parameters['destination']
        results_dict['from'] = parameters['source']
        results_dict['to'] = destination_file
        if (False == self.dry_run):
            try:
                os.makedirs(os.path.dirname(destination_file), exist_ok=True)
                shutil.copyfile(source_file, parameters['destination'])
            except Exception as err:
                results_dict['error_msg'] = str(err)
                return False
        # Now check for and execute any optional parameters
        if ('permissions' in parameters):
            permissions = int(parameters['permissions'], 8)
            if (False == self.dry_run):
                try:
                    os.chmod(destination_file, permissions)
                except Exception as err:
                    results_dict['error_msg'] = str(err)
                    return False
            results_dict['permissions'] = parameters['permissions']
        if ('owner' in parameters) or ('group' in parameters):
            new_owner = parameters['owner'] if 'owner' in parameters else None
            new_group = parameters['group'] if 'group' in parameters else None
            if (False == self.dry_run):
                try:
                    shutil.chown(destination_file, user=new_owner, group=new_group)
                except Exception as err:
                    results_dict['error_msg'] = str(err)
                    return False
            results_dict['owner'] = new_owner
            results_dict['group'] = new_group
        if ('symlink' in parameters):
            symlink_dest = parameters['symlink']
            if (False == self.dry_run):
                os.symlink(destination_file, symlink_dest)
            results_dict['symlink'] = symlink_dest

        return True

    def do_file_delete(self, full_path_filename, results_dict):
        try:
            os.remove(full_path_filename)
        except Exception as err:
            results_dict['error_msg'] = str(err)
            return False
        return True

    def do_directory_delete(self, full_path, results_dict):
        try:
            os.rmdir(full_path)
        except Exception as err:
            results_dict['error_msg'] = str(err)
            return False
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the NEPI Edge SW Manager')
    parser.add_argument('-i','--input_dir', required=True, help='input SOFTWARE directory to process')
    parser.add_argument('-o','--output_dir', default='.', help='output directory for status file')
    parser.add_argument('-d','--dry-run', action="store_true",
                        help='if specified, input folder will be processed but no instructions will be executed; all will report success')
    args = parser.parse_args()

    sw_mgr = NepiEdgeSwMgr()
    sw_mgr.process_sw_folder(sw_folder_path=args.input_dir, results_path=args.output_dir, dry_run=args.dry_run)

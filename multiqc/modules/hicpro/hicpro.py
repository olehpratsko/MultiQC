#!/usr/bin/env python
## Nicolas Servant
## April 2018

""" MultiQC module to parse output from HiCPro """

from __future__ import print_function
from collections import OrderedDict
import os.path
import logging

from multiqc import config
from multiqc.plots import bargraph
from multiqc.modules.base_module import BaseMultiqcModule

# Initialise the logger
log = logging.getLogger(__name__)

class MultiqcModule(BaseMultiqcModule):
    """ HiCPro module, parses log and stats files saved by HiCPro. """

    def __init__(self):

        # Initialise the parent object
        super(MultiqcModule, self).__init__(name='HiCPro', anchor='hicpro',
        href='https://github.com/nservant/HiC-Pro',
        info="is an efficient and flexible pipeline for Hi-C data processing.")

        log.info("Enter HiC-Pro MultiQC module!")
        
        # Find and load any HiC-Pro summary reports
        self.hicpro_data = dict()
        for f in self.find_log_files('hicpro'):
            self.parse_hicpro_stats(f)

        # Update current statistics
        for s_name in self.hicpro_data:
            data = self.hicpro_data[s_name]
            #data['duplicates'] = data['valid_interaction'] - data['valid_interaction_rmdup']
            data['percent_mapped_R1'] = float(data['mapped_R1']) / float(data['total_R1']) * 100
            data['percent_mapped_R2'] = float(data['mapped_R2']) / float(data['total_R2']) * 100
            data['paired_reads'] = int(data['Unique_paired_alignments'] + data['Multiple_pairs_alignments'])
            data['percent_paired_reads'] = float(data['paired_reads'] + data['total_R1']) * 100
            data['percent_valid'] = float(data['valid_interaction']) / float(data['Reported_pairs']) * 100
            data['percent_valid_interaction_rmdup'] = float(data['valid_interaction_rmdup']) / float(data['Reported_pairs']) * 100  
            
        # Filter to strip out ignored sample names
        self.hicpro_data = self.ignore_samples(self.hicpro_data)

        if len(self.hicpro_data) == 0:
            raise UserWarning

        # Find all files for mymod
        #for myfile in self.find_log_files('hicpro'):
        #    print( myfile['fn'] )      # Filename    
        #    print( myfile['s_name'] )  # Sample name (from cleaned filename)
        #    print( myfile['root'] )    # Directory file was in
    
        log.info("Found {} reports".format(len(self.hicpro_data)))
        
        # Write parsed data to a file
        self.write_data_file(self.hicpro_data, 'multiqc_hicpro')

        # Basic Stats Table
        self.hicpro_stats_table()

        # Report sections
        self.add_section (
            name = 'Read Mapping',
            anchor = 'hicpro-mapping',
            description = 'Alignment of reads in single-end mode.',
            helptext = 'HiC-Pro uses a two steps mapping strategy. End-to-end mapping is first performed (*Full reads Alignments*). \
            Unmapped reads are then trimmed at their ligatation site, and the 5\' end is re-aligned on the reference genome (*Trimmed Reads Alignments*)',
            plot = self.hicpro_mapping_chart()
        )

        self.add_section (
            name = 'Read Pairing',
            anchor = 'hicpro-pairing',
            description = 'Pairing of single-end mapping.',
            helptext = 'HiC-Pro combines aligned reads as pairs. Singleton, low quality pairs or pairs involving multi-mapped reads are usually discarded. \
            Note that the filtering at pairing level can change accrding to the parameters used.',
            plot = self.hicpro_pairing_chart()
        )
        
        self.add_section (
            name = 'Read Pair Filtering',
            anchor = 'hicpro-filtering',
            description = 'Filtering of read pairs.',
            helptext = 'Aligned read pairs are filtered to select valid 3C products from two different restriction fragments. \
            Read pairs coming from the same fragments, such as self-ligation or unligated (danging-end) fragments, are discarded. \
            Ligation products involving neighboring restriction fragment (religation) are also discarded. \
            Finaly, as the ligation should be a random process, valid read pairs from all orientations (R=Reverse, F=forward) are expected to be observed at the same proportion.',
            plot = self.hicpro_filtering_chart()
        )

        self.add_section (
            name = 'Contact Statistics',
            anchor = 'hicpro-rmdup',
            description = 'Contacts statistics after duplicates removal.',
            helptext = 'Description of contact frequency after duplicates removal. Intra-chromosomal (*cis*) interaction are expected to be more frequent than inter-chromosomal contacts (*trans*)',
            plot = self.hicpro_contact_chart()
        )

        #self.add_section (
        #     name = 'Length Distribution',
        #     anchor = 'hicpro-lengths',
        #     plot = self.hicpro_insertsize_chart()
        #)

        #self.add_section (
        #     name = 'Capture Statistics',
        #     anchor = 'hicpro-capture',
        #     plot = self.hicpro_capture_chart()
        #)
    
        self.add_section (
            name = 'Allele-specific analysis',
            anchor = 'hicpro-asan',
            description = 'Assignment of valid interactions (afer duplicates removal) to parental alleles.',
            helptext = 'Description of allele-specific contacts. Valid interactions (0-1 and 1-1, resp. 0-2, 2-2) are used to build the genome1 (resp. genome2) parental maps.',
            plot = self.hicpro_as_chart()
        )


    def parse_hicpro_stats(self, f):
        """ Parse a HiCPro stat file """
        s_name = os.path.basename(f['root'])

        ## Check if data already exists
        if s_name in self.hicpro_data.keys():
            data = self.hicpro_data[s_name]
        else:
            data = {}

        for l in f['f'].splitlines():
            if not l.startswith('#'):
                s = l.split("\t")
                data[s[0]] = int(s[1])
                
        if s_name in self.hicpro_data:
            log.debug("Duplicated sample name found! Overwriting: {}".format(s_name))

        self.add_data_source(f, s_name)
        self.hicpro_data[s_name] = data


    def hicpro_stats_table(self):
         """ Add HiC-Pro stats to the general stats table """
         headers = OrderedDict()
         headers['total_R1'] = {
             'title': 'Total',
             'description' : 'Total Number of Read Pairs',
             'min' : '0',
             'scale' : 'RdYlBu',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_keys' : 'read_count'
         }

         headers['mapped_R1'] = {
             'title': 'Aligned [R1]',
             'description' : 'Total number of aligned reads [R1] ({})'.format(config.read_count_desc),
             'min' : '0',
             'scale' : 'RdYlBu',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_keys' : 'read_count'
         }

         headers['percent_mapped_R1'] = {
             'title': '% Aligned [R1]',
             'description': 'Percentage of aligned reads [R1] (%)',
             'max': 100,
             'min': 0,
             'suffix': '%',
             'scale': 'YlGn'
         }

         headers['mapped_R2'] = {
             'title': 'Aligned [R2]',
             'description' : 'Total number of aligned reads [R2] ({})'.format(config.read_count_desc),
             'min' : '0',
             'scale' : 'RdYlBu',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_keys' : 'read_count'
         }

         headers['percent_mapped_R2'] = {
             'title': '% Aligned [R2]',
             'description': 'Percentage of aligned reads [R2] (%)',
             'max': 100,
             'min': 0,
             'suffix': '%',
             'scale': 'YlGn'
         }

         headers['paired_reads'] = {
             'title': 'Paired reads',
             'description' : 'Total number of paired reads ({})'.format(config.read_count_desc),
             'min' : '0',
             'scale' : 'RdYlBu',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_keys' : 'read_count'
         }

         headers['percent_paired_reads'] = {
             'title': '% Paired reads',
             'description': 'Percentage of paired reads (%)',
             'max': 100,
             'min': 0,
             'suffix': '%',
             'scale': 'YlGn'
         }

         headers['valid_interaction'] = {
             'title': '{} Valid Pairs'.format(config.read_count_prefix),
             'description': 'Number of valid pairs ({})'.format(config.read_count_desc),
             'min': 0,
             'scale': 'RdYlBu',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_key': 'read_count'
         }
         
         headers['percent_valid'] = {
             'title': '% Valid Pairs',
             'description': 'Percentage of valid pairs over reported ones (%)',
             'max': 100,
             'min': 0,
             'suffix': '%',
            'scale': 'YlGn'
         }
         
         headers['valid_interaction_rmdup'] = {
             'title': '{} Valid Pairs Unique'.format(config.read_count_prefix),
             'description': 'Number of valid pairs after duplicates removal ({})'.format(config.read_count_desc),
             'min': 0,
             'scale': 'PuRd',
             'modify': lambda x: x * config.read_count_multiplier,
             'shared_key': 'read_count'
         }
         
         headers['percent_valid_interaction_rmdup'] = {
             'title': '% Valid Pairs Unique',
             'description': 'Percent of valid pairs over reported ones after duplicates removal (%)',
             'max': 100,
             'min': 0,
             'suffix': '%',
             'scale': 'YlGn-rev',
             'modify': lambda x: 100 - x
         }
     
         self.general_stats_addcols(self.hicpro_data, headers, 'HiC-Pro')


    def hicpro_mapping_chart (self):
        """ Generate the HiC-Pro Aligned reads plot """

        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys['Full_Alignments_Read']   = { 'color': '#005ce6', 'name': 'Full reads Alignments' }
        keys['Trimmed_Alignments_Read'] = { 'color': '#3385ff', 'name': 'Trimmed reads Alignments' }
        keys['Failed_To_Align_Read']     = { 'color': '#a9a2a2', 'name': 'Failed To Align' }
    
        # Construct a data structure for the plot - duplicate the samples for read 1 and read 2
        data = {}
        for s_name in self.hicpro_data:
            data['{} Read 1'.format(s_name)] = {}
            data['{} Read 2'.format(s_name)] = {}
            data['{} Read 1'.format(s_name)]['Full_Alignments_Read'] = self.hicpro_data[s_name]['global_R1']
            data['{} Read 2'.format(s_name)]['Full_Alignments_Read'] = self.hicpro_data[s_name]['global_R2']
            data['{} Read 1'.format(s_name)]['Trimmed_Alignments_Read'] = self.hicpro_data[s_name]['local_R1']
            data['{} Read 2'.format(s_name)]['Trimmed_Alignments_Read'] = self.hicpro_data[s_name]['local_R2']
            data['{} Read 1'.format(s_name)]['Failed_To_Align_Read'] = int(self.hicpro_data[s_name]['total_R1']) - int(self.hicpro_data[s_name]['mapped_R1'])
            data['{} Read 2'.format(s_name)]['Failed_To_Align_Read'] = int(self.hicpro_data[s_name]['total_R2']) - int(self.hicpro_data[s_name]['mapped_R2'])

        # Config for the plot
        config = {
            'id': 'hicpro_mapping_stats_plot',
            'title': 'HiC-Pro: Mapping Statistics',
            'ylab': '# Reads',
            'cpswitch_counts_label': 'Number of Reads'
        }

        return bargraph.plot(data, keys, config)

    def hicpro_pairing_chart (self):
        """ Generate Pairing chart """

        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys['Unique_Pairs'] = { 'color': '#005ce6', 'name': 'Uniquely Aligned' }
        keys['Low_Qual_Pairs'] = { 'color': '#ff8533', 'name': 'Low Quality' }
        keys['Singleton_Pairs'] = { 'color': ' #ff9933', 'name': 'Singleton' }
        keys['Multi_Pairs'] = { 'color': '#e67300', 'name': 'Multi Aligned' }
        keys['Failed_To_Align_Pairs'] = { 'color': '#a9a2a2', 'name': 'Failed To Align' }
    
        # Construct a data structure for the plot - duplicate the samples for read 1 and read 2
        data = {}
        for s_name in self.hicpro_data:
            data['{} Pairs'.format(s_name)] = {}
            data['{} Pairs'.format(s_name)]['Failed_To_Align_Pairs'] = self.hicpro_data[s_name]['Unmapped_pairs']
            data['{} Pairs'.format(s_name)]['Low_Qual_Pairs'] = self.hicpro_data[s_name]['Low_qual_pairs']
            data['{} Pairs'.format(s_name)]['Unique_Pairs'] = self.hicpro_data[s_name]['Unique_paired_alignments']
            data['{} Pairs'.format(s_name)]['Multi_Pairs'] = self.hicpro_data[s_name]['Multiple_pairs_alignments']
            data['{} Pairs'.format(s_name)]['Singleton_Pairs'] = self.hicpro_data[s_name]['Pairs_with_singleton']

        print ( data )
        # Config for the plot
        config = {
        'id': 'hicpro_pairing_stats_plot',
            'title': 'HiC-Pro: Pairing Statistics',
            'ylab': '# Reads',
            'cpswitch_counts_label': 'Number of Reads'
        }

        return bargraph.plot(data, keys, config)

        
    def hicpro_filtering_chart (self):
        """ Generate the HiC-Pro filtering plot """

        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys['Valid_interaction_pairs_FF'] = { 'color': '#ccddff', 'name': 'Valid Pairs FF' }
        keys['Valid_interaction_pairs_RR'] = { 'color': '#6699ff', 'name': 'Valid Pairs RR' }
        keys['Valid_interaction_pairs_RF'] = { 'color': '#0055ff', 'name': 'Valid Pairs RF' }
        keys['Valid_interaction_pairs_FR'] = { 'color': '#003399', 'name': 'Valid Pairs FR' }
        keys['Self_Cycle_pairs'] = { 'color': '#ffad99', 'name': 'Same Fragment - Self-Circle' }
        keys['Dangling_end_pairs'] = { 'color': '#ff5c33', 'name': 'Same Fragment - Dangling Ends' }
        keys['Religation_pairs'] = { 'color': '#cc2900', 'name': 'Re-ligation' }
        keys['Dumped_pairs'] = { 'color': '#661400', 'name': 'Dumped pairs' }

        # Config for the plot
        config = {
            'id': 'hicpro_filtering_plot',
            'title': 'HiC-Pro: Filtering Statistics',
            'ylab': '# Read Pairs',
            'cpswitch_counts_label': 'Number of Read Pairs',
            'cpswitch_c_active': False
        }
        
        return bargraph.plot(self.hicpro_data, keys, config)

    def hicpro_contact_chart (self):
        """ Generate the HiC-Pro interaction plot """

        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys['cis_shortRange'] = { 'color': '#0039e6', 'name': 'Unique: cis <= 20Kbp' }
        keys['cis_longRange'] = { 'color': '#809fff', 'name': 'Unique: cis > 20Kbp' }
        keys['trans_interaction']  = { 'color': '#009933', 'name': 'Unique: trans' }
        keys['duplicates'] = { 'color': '#a9a2a2', 'name': 'Duplicate read pairs' }
        
        # Config for the plot
        config = {
            'id': 'hicpro_contact_plot',
            'title': 'HiC-Pro: Contact Statistics',
            'ylab': '# Pairs',
            'cpswitch_counts_label': 'Number of Pairs',
            'cpswitch_c_active': False
        }
        
        return bargraph.plot(self.hicpro_data, keys, config)
  
    def hicpro_as_chart (self):
        """ Generate Allele-specific plot"""
        
        keys = OrderedDict()
        keys['Valid_pairs_from_ref_genome_(1-1)'] = { 'color': '#e6550d', 'name': 'Genome1 specific read pairs (1-1)' }
        keys['Valid_pairs_from_ref_genome_with_one_unassigned_mate_(0-1/1-0)'] = { 'color': '#fdae6b', 'name': 'Genome1 with one unassigned mate (0-1/1-0)' }
        keys['Valid_pairs_from_alt_genome_(2-2)']  = { 'color': '#756bb1', 'name': 'Genome2 specific read pairs (2-2)' }
        keys['Valid_pairs_from_alt_genome_with_one_unassigned_mate_(0-2/2-0)'] = { 'color': '#bcbddc', 'name': 'Genome2 with one unassigned mate (0-2/2-0)' }
        keys['Valid_pairs_from_alt_and_ref_genome_(1-2/2-1)'] = { 'color': '#a6611a', 'name': 'Trans homologuous read pairs (1-2/2/1)' }
        keys['Valid_pairs_with_both_unassigned_mated_(0-0)'] = { 'color': '#cccccc', 'name': 'Unassigned read pairs' }
        keys['Valid_pairs_with_at_least_one_conflicting_mate_(3-)'] = { 'color': '#a9a2a2', 'name': 'Conflicting read pairs' }

        # Config for the plot
        config = {
            'id': 'hicpro_asan_plot',
            'title': 'HiC-Pro: Allele-specific Statistics',
            'ylab': '# Pairs',
            'cpswitch_counts_label': 'Number of Pairs',
            'cpswitch_c_active': False
        }

        return bargraph.plot(self.hicpro_data, keys, config)

                
    def hicpro_capture_chart (self):
        """ Generate capture plot"""

    def hicpro_insertsize_chart (self):
        """ Generate insert size histogram"""



        

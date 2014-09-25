#!/usr/bin/env python

'''
This script parses a JSON file output by Karma which contains mentions
and converts these to features and outputs a single FC chunk file.

Its architecture is that of a mini pipeline: define global functions
prefixed with ``trans_`` and run them using the ``--transform`` command
line option.
'''

from __future__ import absolute_import, division, print_function

import argparse
from collections import defaultdict
import json
import os
import io

from dossier.fc import \
    FeatureCollection, FeatureCollectionCborChunk, StringCounter

HTML_TABLE = u'<table><tr><th>Attr</th><th>Values</th></tr>{rows}</table>'
HTML_TR = u'<tr><td>{attr}</td><td>{vals}</td></tr>'

def group_mentions_as_features(jsonfile):
    '''
    Groups features from the json file coming from karma [which isn't really json]
    '''
    grouped = defaultdict(dict)

    json_array = json.load(jsonfile, "utf-8")
    for item in json_array:
        obj_id = item['@id']
        if 'schema:mentions' in item:
            mentions = item['schema:mentions']
            if isinstance(mentions, list) and len(mentions) > 1:
                for mention in item['schema:mentions']:
                    feature = mention['memex:feature']
                    feature_splits = feature.rsplit('/', 2)
                    featname = feature_splits[1]
                    featval = feature_splits[2]
                    grouped[obj_id].setdefault(featname, []).append(featval)
            else:
                # This means mentions is a single object
                mention = mentions
                feature = mention['memex:feature']
                feature_splits = feature.rsplit('/', 2)
                featname = feature_splits[1]
                featval = feature_splits[2]
                grouped[obj_id].setdefault(featname, []).append(featval)
    return grouped

def trans_display(fc, adid, attrvals):
    '''
    :type fc: FeatureCollection
    :type adid: str
    :type attrvals: featname |--> [featval]
    '''
    rows = []
    for attr, vals in attrvals.iteritems():
        rows.append(HTML_TR.format(attr=attr, vals=', '.join(vals)))
    fc['display'] = HTML_TABLE.format(rows='\n'.join(rows))

def trans_features(fc, adid, attrvals):
    '''
    create features from json file
    also create Bag of Soft Biometric traits (bosb)

    :type fc: FeatureCollection
    :type adid: str
    :type attrvals: featname |--> [featval]
    '''

    ## this list can be adjusted as needed
    appearance_set = set(['weight', 'height', 'ethnicity', 'age', 'hair', 
                          'hairlength', 'hairtype', 'tattoos', 'build', 'cup', 
                          'grooming', 'implants', 'piercings' ])

    ## create bosb
    fc['bosb'] = StringCounter()

    for attr, vals in attrvals.iteritems():
        fc[attr] = StringCounter()
        for val in vals:
            ## create a feature for each attribute
            fc[attr][val] += 1

        ## populate bosb
        if attr in appearance_set:
            for val in vals:
                feature = attr + '-' + val
                fc['bosb'][feature] += 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description='Convert Karma JSON file to FeatureCollections.')
    p.add_argument('karma_json', metavar='JSON_FILE')
    p.add_argument('fc_chunk', metavar='FC_CHUNK_FILE')
    p.add_argument('--transforms', action='append')
    p.add_argument('--overwrite', action='store_true')
    args = p.parse_args()

    if args.overwrite:
        try:
            os.unlink(args.fc_chunk)
        except OSError:
            pass

    with open(args.karma_json) as fjson:
        grouped = group_mentions_as_features(fjson)

    chunk = FeatureCollectionCborChunk(path=args.fc_chunk, mode='wb')
    for adid, attrvals in grouped.iteritems():
        fc = FeatureCollection()
        fc['adid'] = adid
        fc['attrvals'] = json.dumps(attrvals).decode('utf-8')
        fc['NAME'] = StringCounter({adid: 1})
        for trans in args.transforms:
            globals()['trans_%s' % trans](fc, adid, attrvals)
        chunk.add(fc)
    chunk.flush()
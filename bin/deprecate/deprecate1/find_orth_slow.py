#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#  Copyright © xh
# CreateTime: 2016-06-03 13:55:13

# this is the py version of blast
import sys
import networkx as nx
from math import log10
import os
from commands import getoutput
from mmap import mmap, ACCESS_WRITE, ACCESS_READ
from collections import Counter


# print the manual
def manual_print():
    print 'Usage:'
    print '    python fast_search.py -i foo.sc [-c .5] [-y 50] [-n no]'
    print 'Parameters:'
    print '  -i: tab-delimited file which contain 14 columns'
    print '  -c: min coverage of sequence [0~1]'
    print '  -y: identity [0~100]'
    print '  -n: normalization score [no|bsr|bal]. bsr: bit sore ratio; bal:  bit score over anchored length. Default: no'
    print '  -a: cpu number for sorting. Default: 1'
    print '  -t: keep tmpdir[y|n]. Default: n'


argv = sys.argv
# recommand parameter:
args = {'-i':'', '-c':.5, '-y':0, '-n':'no', '-t':'n', '-a':'4'}

N = len(argv)
for i in xrange(1, N):
    k = argv[i]
    if k in args:
        try:
            v = argv[i+1]
        except:
            break
        args[k] = v
    elif k[:2] in args and len(k) > 2:
        args[k[:2]] = k[2:]
    else:
        continue

if args['-i']=='':
    manual_print()
    raise SystemExit()

try:
    qry, coverage, identity, norm, tmpdir, np = args['-i'], float(args['-c']), float(args['-y']), args['-n'], args['-t'], int(args['-a'])
except:
    manual_print()
    raise SystemExit()


#qry = sys.argv[1]
qry = os.path.abspath(qry)
fn = qry.split(os.sep)[-1]
os.system('mkdir -p %s_tmp/'%qry)
os.system('ln -sf %s %s_tmp/'%(qry, qry))
qry = qry + '_tmp/' + fn

# blast parser, return list contains blast results with the same query id
# remove the duplicated pairs or qid-sid
def blastparse(f, coverage = .5, identity = 0., norm='no', len_dict = {}):
    output = {}
    #len_dict = {}
    flag = None
    # max bit score
    mbsc = -1
    for i in f:
        j = i[: -1].split('\t')
        qid, sid = j[:2]
        qtx, stx = qid.split('|')[0], sid.split('|')[0]
        #key = qtx == stx and sid or stx
        key = sid

        idy, aln, mis, gop, qst, qed, sst, sed, evalue, score = map(float, j[2:12])
        # the fastclust seq search format
        if len(j) > 13:
            qln, sln = map(float, j[12:14])
        else:
            if qid in len_dict:
                qln = len_dict[qid]
            else:
                qln = max(qst, qed)
                len_dict[qid] = qln
            if sid in len_dict:
                sln = len_dict[sid]
            else:
                sln = max(sst, sed)
                len_dict[sid] = sln


        qcv = (1.+abs(qed-qst))/qln
        scv = (1.+abs(sed-sst))/sln
        if qcv<coverage or scv<coverage or idy<identity:
            continue

        if flag != qid:
            if output:
                yield output.values()

            mbsc = score
            #print 'max bit score is', mbsc, qid, sid
            output = {}
            length = aln
            flag = qid
            if norm == 'bsr':
                Score = score / mbsc
            elif norm == 'bal':
                Score = score / aln
            else:
                Score = score
            output[key] = [qid, sid, Score]
        else:

            if norm == 'bsr':
                Score = score / mbsc
            elif norm == 'bal':
                Score = score / aln
            else:
                Score = score

            if key not in output or output[key][-1]<Score:
                output[key] = [qid, sid, Score]

    if output:
        yield output.values()


# distinguish IP and O
# return the IP and O
def get_IPO(hits):
    # get max of each species
    sco_max = Counter()
    out_max = 0
    for hit in hits:
        qid, sid, sco = hit
        sco = float(sco)
        qtx = qid.split('|')[0]
        stx = sid.split('|')[0]
        sco_max[stx] = max(sco_max[stx], sco)
        if qtx != stx:
            out_max = max(out_max, sco)

    visit = set()
    ips, ots, cos  = [], [], []
    for hit in hits:
        qid, sid, sco = hit
        sco = float(sco)
        if sid in visit:
            continue
        else:
            visit.add(sid)
        qtx = qid.split('|')[0]
        stx = sid.split('|')[0]
        out = qid < sid and [qid, sid, sco] or [sid, qid, sco]
        out = '\t'.join(map(str, out)) + '\n'
        if qtx == stx:
            if sco >= out_max:
                #ips.append(hit)
                ips.append(out)
            else:
                continue
        else:
            if sco >= sco_max[stx]:
                #ots.append(hit)
                ots.append(out)
            else:
                cos.append(out)

    return ips, ots, cos

# parse and find IP, O from blast results
len_dict = {}
f = open(qry, 'r')
for i in f:
    j = i.split('\t')
    if len(j) > 13:
        break
    qid, sid = j[:2]
    idy, aln, mis, gop, qst, qed, sst, sed, evalue, score = map(float, j[2:12])
    len_dict[qid] = max(qst, qed, len_dict.get(qid, 0))
    len_dict[sid] = max(sst, sed, len_dict.get(sid, 0))
   
f.close()

f = open(qry, 'r')
qip = qry + '.qIPs.txt'
_oIPs = open(qip, 'w')

qo = qry + '.qOs.txt'
_oOs = open(qo, 'w')

qco = qry + '.qCOs.txt'
_oCOs = open(qco, 'w')

flag_co = 0
for i in blastparse(f, coverage, identity, norm, len_dict):
    IPs, Os, COs = get_IPO(i)
    #print IPs, Os
    _oIPs.writelines(IPs)
    _oOs.writelines(Os)
    _oCOs.writelines(COs)
    flag_co += len(COs)


_oIPs.close()
_oOs.close()
_oCOs.close()


# sort QIP and QO
qipsort = qip + '.sort'
os.system('export LC_ALL=C && sort --parallel=%s -k1,2 %s -o %s;mv %s %s'%(np, qip, qipsort, qipsort, qip))

qosort = qo + '.sort'
os.system('export LC_ALL=C && sort --parallel=%s -k1,2 %s -o %s;mv %s %s'%(np, qo, qosort, qosort, qo))

# get IPs and Os
def find_IPO(f):
    flag = None
    output = []
    for i in f:
        j = i[:-1].split('\t')
        qid, sid, score = j
        if flag != j[:2]:
            if len(output) == 4:
                yield output[0], output[1], sum(output[2:]) / 2., 1
            elif len(output) == 3:
                yield output[0], output[1], output[2], 0
            else:
                pass
            flag = j[:2]
            output = [qid, sid, float(score)]
        else:
            output.append(float(score))

    if len(output) == 4:
        yield output[0], output[1], sum(output[2:]) / 2., 1
    elif len(output) == 3:
        yield output[0], output[1], output[2], 0
    else:
        pass


# get IP
ipn = qry + '.IPs.txt'
_o = open(ipn, 'w')
f = open(qip, 'r')
for qid, sid, score, flag in find_IPO(f):
    if flag == 1:
        _o.write('%s\t%s\t%f\n'%(qid, sid, score))

_o.close()

# get O
_oCOs = open(qco, 'a')

osn = qry + '.Os.txt'
_o = open(osn, 'w')
f = open(qo, 'r')
for qid, sid, score, flag in find_IPO(f):
    if flag == 1:
        _o.write('%s\t%s\t%f\n'%(qid, sid, score))
    else:
        if qid > sid:
            qid, sid = sid, qid
        _oCOs.write('%s\t%s\t%f\n'%(qid, sid, score))

_o.close()


qcosort = qco + '.sort'
# sort qCOs
os.system('export LC_ALL=C && sort --parallel=%s -k1,2 %s -o %s;mv %s %s'%(np, qco, qcosort, qcosort, qco))

# get CO
# correct the position
# binary search by lines
correct0 = lambda s, i: s.rfind('\n', 0, i) + 1
def binary_search0(s, p, L = 0, R = -1):
    n = len(s)
    pn = len(p)
    R = R == -1 and n - 1 or R
    l = correct(s, L)
    r = correct(s, R)
    # find left
    end = pn
    while l <= r:
        m = (l + r) // 2
        m = correct(s, m)
        if m == l:
            if s[m: end] >= p:
                r = m
            else:
                l = m
            break
        end = m + pn
        if s[m: end] >= p:
            r = m
        else:
            l = m

    left = r
    if s[left: left + pn] != p:
        pairs = s[-1: -1].split('\n')
        return -1, -1, pairs

    right = r
    while 1:
        right = s.find('\n', right)
        if right != -1 and s[right + 1: right + 1 + pn] == p:
            right += 1
        else:
            break

    pairs = s[left: right].split('\n')
    return left, right, pairs


# correct the position
def correct1(s, m, l=None, r=None):
    if not l and not r:
        return s.rfind('\n', 0, m) + 1
    M = s.rfind('\n', l, m) + 1
    if l < M < r:
        return M
    else:
        M = s.find('\n', m, r) + 1
        return M

def binary_search1(s, p, key=lambda x:x.split('\t', 1)[0], L = 0, R = -1):
    mx = chr(255)
    n = len(s)
    pn = len(p)
    R = R == -1 and n - 1 or R
    l = correct(s, L)
    r = correct(s, R)
    # find left
    while l < r:
        m = (l + r) // 2
        m = correct(s, m, l, r)
        if m == l or m == r:
            break
        t = s[m: s.find('\n', m)]
        pat = key(t)
        #if pat[:pn] >= p:
        if pat+mx >= p+mx:
            r = m
        else:
            l = m

    # search from both direction
    left = r - 1
    while left >= 0:
        start = s.rfind('\n', 0, left)
        line = s[start+1: left]
        if key(line).startswith(p):
            left = start
        else:
            break
    left += 1

    line = s[left: s.find('\n', left)]
    if not key(line).startswith(p):
        pairs = s[-1: -1].split('\n')
        return -1, -1, pairs

    right = left
    while 1:
        end = s.find('\n', right)
        if key(s[right: end]).startswith(p):
            right = end + 1
        else:
            break

    pairs = s[left: right].strip().split('\n')
    return left, right, pairs


# correct search results
def correct(s, m, l=None, r=None, sep='\n'):
    if not l and not r:
        return s.rfind(sep, 0, m) + 1
    M = s.rfind(sep, l, m) + 1
    if l < M < r:
        return M
    else:
        M = s.find(sep, m, r) + 1
        return M

def binary_search(s, p, key=lambda x:x.split('\t', 1)[0], L=0, R=-1, sep='\n'):
    #mx = chr(255)
    n = len(s)
    pn = len(p)
    R = R == -1 and n-1 or R
    l = correct(s, L, sep=sep)
    r = correct(s, R, sep=sep)
    # find left
    while l < r:
        m = (l + r) // 2
        m = correct(s, m, l, r, sep=sep)
        if m == l or m == r:
            break
        t = s[m: s.find('\n', m)]
        pat = key(t)
        #if pat[:pn] >= p:
        #if pat+mx >= p+mx:
        if pat >= p:
            r = m
        else:
            l = m

    #print 'mid is', key(s[m: s.find('\n', m)]), p

    # search from both direction
    #left = r - 1
    left = m - 1
    while left >= 0:
        start = s.rfind('\n', 0, left)
        line = s[start+1: left]
        #if key(line).startswith(p):
        if key(line) == p:
            left = start
        else:
            break
    left += 1

    line = s[left: s.find('\n', left)]
    #if not key(line).startswith(p):
    if key(line) != p:
        return -1, -1, []

    right = left
    while 1:
        end = s.find('\n', right)
        #if key(s[right: end]).startswith(p):
        if key(s[right: end]) == p:
            right = end + 1
        else:
            break

    pairs = s[left: right].strip().split('\n')
    return left, right, pairs


# sort the IPs by k2
os.system("awk '{print $2\"\\t\"$1\"\\t\"$3}' %s > %s.tmp; export LC_ALL=C && sort --parallel=%s -k1 %s.tmp -o %s.k2; rm %s.tmp"%(ipn, ipn, np, ipn, ipn, ipn))
ipnk2 = ipn + '.k2'
f0k2 = open(ipnk2, 'r')
try:
    S0k2 = mmap(f0k2.fileno(), 0, access = ACCESS_READ)
except:
    S0k2 = None

f0 = open(ipn, 'r')
try:
    S0 = mmap(f0.fileno(), 0, access = ACCESS_READ)
except:
    S0 = None

f1 = open(osn, 'r')
try:
    S1 = mmap(f1.fileno(), 0, access = ACCESS_READ)
except:
    S1 = None

f2 = open(qco, 'r')
try:
    S2 = mmap(f2.fileno(), 0, access = ACCESS_READ)
except:
    S2 = None

cosn = qry + '.COs.txt'
_o = open(cosn, 'w')
for i in f1:
    qo, so = i.split('\t')[:2]
    qip = set([qo])
    try:
        L0, R0, pairs0 = binary_search(S0, qo)
    except:
        L0 = R0 = -1
        pairs0 = []
    try:
        L1, R1, pairs1 = binary_search(S0k2, qo)
    except:
        L1 = R1 = -1
        pairs1 = []
    for j in pairs0 + pairs1:
        if j:
            a, b = j.split('\t')[: 2]
            if a != qo:
                continue
            qip.add(a)
            qip.add(b)

    sip = set([so])
    try:
        L0, R0, pairs0 = binary_search(S0, so)
    except:
        L0 = R0 = -1
        pairs0 = []
    try:
        L1, R1, pairs1 = binary_search(S0k2, so)
    except:
        L1 = R1 = -1
        pairs1 = []
    for j in pairs0 + pairs1:
        if j:
            a, b = j.split('\t')[: 2]
            if a != so:
                continue
            sip.add(a)
            sip.add(b)

    #print 'qip', qip, 'sip', sip
    for i in qip:
        for j in sip:
            if (i==qo and j==so) or (i==so and j==qo) or (i==j):
                continue
            key = i < j and i + '\t' + j or j + '\t' + i
            try:
                L, R, pairs = binary_search(S2, key, lambda x: '\t'.join(x.split('\t', 3)[:2]))
                #print 'pairs', pairs, S2, key
            except:
                L = R = -1
                pairs = []
            outs = [elem for elem in pairs if elem.strip()]
            if outs:
                out = outs[0]
                _o.write(out+'\n')
            else:
                continue

_o.close()

f0k2.close()
f0.close()
f1.close()
f2.close()

# normalization
# IP
ipqa = Counter()
ipqa_n = Counter()
ipqA = Counter()
ipqA_n = Counter()
f = open(ipn, 'r')

for i in f:
    qid, sid, score = i[:-1].split('\t')
    score = float(score)
    tax = qid.split('|')[0]
    ipqA[tax] += score
    ipqA_n[tax] += 1.
    qL, qR, qpairs = binary_search(S1, qid)
    sL, sR, spairs = binary_search(S1, sid)
    if qL!=-1 and sL!=-1 and qR!=-1 and sR!=-1:
        ipqa[tax] += score
        ipqa_n[tax] += 1

f.close()


for i in ipqA:
    n = ipqa_n[i]
    if n > 0:
        ipqa[i] /= n
    else:
        ipqa[i] = ipqA[i] / ipqA_n[i]

del ipqA, ipqA_n, ipqa_n


f = open(ipn, 'r')
for i in f:
    qid, sid, score = i[:-1].split('\t')
    tax = qid.split('|')[0]
    n = ipqa[tax]
    score = float(score)
    #out = map(str, ['IP', qid, sid, score/n])
    try:
        out = map(str, ['IP', qid, sid, score/n])
    except:
        #print 'score is', tax, tax in ipqa, out
        continue
    print '\t'.join(out)

f.close()
del ipqa



# co and o
# sort blast with taxon name
# normal co and o
def normal_co_o(f):
    flag = None
    out = []
    for i in f:
        qtax, stax, typ, qid, sid, score = i[:-1].split('\t')
        score = float(score)
        if (qtax, stax) != flag:
            if out:
                yield out
            flag = (qtax, stax)
            out = [[qtax, stax, typ, qid, sid, score]]
        else:
            out.append([qtax, stax, typ, qid, sid, score])
    if out:
        yield out

# the co
_o = open(cosn+'.tmp', 'w')
f = open(cosn, 'r')
for i in f:
    qid, sid, score = i[:-1].split('\t')[:3]
    qtax = qid.split('|')[0]
    stax = sid.split('|')[0]
    out = [qtax, stax, 'CO', qid, sid, score]
    _o.write('\t'.join(out)+'\n')

f.close()
_o.close()

#os.system('sort --parallel=%s -k1,2 %s.tmp | uniq > %s.tmp.srt'%(np, cosn, cosn))
os.system('export LC_ALL=C && sort --parallel=%s -k1,2 %s.tmp -o %s.tmp.srt.tmp && rm %s.tmp && uniq %s.tmp.srt.tmp > %s.tmp.srt'%(np, cosn, cosn, cosn, cosn, cosn))


f = open(cosn+'.tmp.srt', 'r')
for i in normal_co_o(f):
    avg = sum([elem[-1] for elem in i]) * 1. / len(i)
    for j in i:
        qtax, stax, typ, qid, sid, score = j
        score = float(score)/avg
        typ = qid == sid and 'IP' or typ
        print '\t'.join(map(str, [typ, qid, sid, score]))

f.close()


# the os
_o = open(osn+'.tmp', 'w')
f = open(osn, 'r')
for i in f:
    qid, sid, score = i[:-1].split('\t')[:3]
    qtax = qid.split('|')[0]
    stax = sid.split('|')[0]
    out = map(str, [qtax, stax, 'O', qid, sid, score])
    _o.write('\t'.join(out)+'\n')

f.close()
_o.close()

#os.system('sort --parallel=%s -k1,2 %s.tmp | uniq > %s.tmp.srt'%(np, osn, osn))
os.system('export LC_ALL=C && sort --parallel=%s -k1,2 %s.tmp -o %s.tmp.srt.tmp && rm %s.tmp && uniq %s.tmp.srt.tmp > %s.tmp.srt'%(np, osn, osn, osn, osn, osn))


f = open(osn+'.tmp.srt', 'r')
for i in normal_co_o(f):
    avg = sum([elem[-1] for elem in i]) * 1. / len(i)
    for j in i:
        qtax, stax, typ, qid, sid, score = j
        score = float(score)/avg
        typ = qid == sid and 'IP' or typ
        #print '\t'.join([typ, qid, sid, score])
        print '\t'.join(map(str, [typ, qid, sid, score]))


f.close()

if tmpdir == 'n':
    os.system('rm -rf %s_tmp/'%qry)

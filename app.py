from pathlib import Path
import hashlib
import re
import pandas as pd
import plotly.express as px
import streamlit as st

QUESTIONS = {'date': 'Start Date', 'duration_minutes': 'Duration (minutes)', 'duration_days': 'Duration (days)', 'eligible': 'Are you currently physically located in the United States?', 'role': 'How would you describe your primary role on campus?', 'age': 'How old are you?', 'telecommute': 'How often do you telecommute? (work or attend classes remotely)', 'zip': 'What is the zip code of your place of residence?', 'campus_days': 'If you live off-campus, how many DAYS do you come to the campus per week?', 'campus_trips': 'If you live on-campus, how many TRIPS per week do you make from your place of residence to your class/work/recreational activities on-campus?', 'distance': 'How many miles is your place of residence from your destination on campus? (your lab/first class of the day or your work)', 'commute_time': 'How long does your commute to campus typically take?', 'mode': 'What is your primary means of transportation from your place of residence to your first campus destination on a typical weekday?', 'supplement': 'In general, do you supplement your primary mode of commuting to campus with another method? (check all that apply)', 'rank': 'Rank your preferred mode of transportation? (Rank up to 5) - Reorder according to your preference', 'campus_mode': 'On a typical weekday, how do you travel once you arrive on campus? (To travel between classes, to go for meetings, etc.)', 'bus_barriers': 'What reasons make you less likely to commute via bus to campus? (Check up to 5)', 'permit': 'Do you have a campus parking permit?', 'parking': 'If you drive to campus, how difficult is it to find parking?', 'incentives': 'What programs or incentives would encourage you to relinquish your parking pass and to carpool or use an active mode of transportation to travel to/around campus?', 'driving_reasons': 'On days you drive alone to work, what are your most common reasons for doing so? (check up to 5)', 'bike_owner': 'Do you own a bike?', 'bike_frequency': 'How often do you ride a bike?', 'walk_improvements': 'What improvements would make walking a more attractive mode of transportation on campus for you? (Check up to 5)', 'bike_improvements': 'What improvements would make biking a more attractive mode of transportation on campus for you? (Check up to 5)', 'walk_safety': 'How safe do you feel when navigating campus while walking?', 'bike_safety': 'How safe do you feel when navigating campus while riding a bicycle?', 'accessibility': 'If you have a disability that affects how you navigate the campus, how would you describe your experience using sidewalks, crossings, intersections, and other transportation infrastructure?', 'safety_comments': 'In your own words, what are your biggest safety concerns when navigating campus, and what improvements would make you feel safer?', 'network_comments': 'What is your overall perception of the campus transportation network? What improvements would you like to see to enhance the campus experience?'}
MULTI = ['supplement', 'bus_barriers', 'incentives', 'driving_reasons',
         'walk_improvements', 'bike_improvements']
NUMERIC = ['duration_minutes', 'duration_days', 'campus_days', 'campus_trips', 'distance']

def clean(value):
    if pd.isna(value):
        return None
    return re.sub(r'\s+', ' ', str(value).replace('\xa0', ' ')).strip() or None

def load_survey(source):
    raw = pd.read_excel(source, sheet_name=0)
    headers = {clean(c): c for c in raw.columns}
    missing = [q for k, q in QUESTIONS.items() if k != 'zip' and q not in headers]
    if missing:
        raise ValueError('Workbook columns do not match this survey. Missing: ' + '; '.join(missing))
    # ZIP codes are deliberately excluded from the analytical frame.
    data = pd.DataFrame({k: raw[headers[q]] for k, q in QUESTIONS.items() if k != 'zip'})
    for k in data.columns:
        if k == 'date':
            data[k] = pd.to_datetime(data[k], errors='coerce')
        elif k in NUMERIC:
            data[k] = pd.to_numeric(data[k], errors='coerce')
        else:
            data[k] = data[k].map(clean)
    data['role_group'] = data['role'].map(lambda v: v if v in ['Staff', 'Student', 'Faculty'] else ('Other / multiple roles' if v else 'Missing'))
    return data

def tokens(value):
    if not value or pd.isna(value):
        return []
    return list(dict.fromkeys(t for t in (clean(s) for s in value.split(';')) if t))

def summary(data, key, multi=False, ranked_first=False):
    answered = data[key].dropna()
    if multi or ranked_first:
        selections = answered.map(tokens)
        selections = selections[selections.map(bool)]
        if ranked_first:
            selections = selections.map(lambda a: a[:1])
        counts = selections.explode().value_counts()
        denominator = len(selections)
    else:
        counts = answered.value_counts()
        denominator = len(answered)
    result = counts.rename_axis('Response').reset_index(name='Respondents')
    result['Percent'] = result['Respondents'] / denominator * 100 if denominator else 0.0
    result['Answered'] = denominator
    return result

def rate(data, key, predicate):
    values = data[key].dropna()
    return (values.map(predicate).mean() * 100, len(values)) if len(values) else (None, 0)


# Theme definitions, inclusion guidance, and provisional text rules are deliberately visible.
# These rules suggest codes; they do not constitute validated qualitative coding.
CODEBOOK = {
    'Transit operations': {
        'definition': 'Bus frequency, waiting, punctuality, crowding, transfers, or journey time.',
        'exclude': 'A generic mention of a bus without an operational issue or suggestion.',
        'pattern': r'(?is)^(?=.*\b(bus(?:es|ses)?|mtd|transit|shuttle|teal|gold|illini)\b)(?=.*(?:frequen|crowd|reliab|unreliab|late\b|delay|wait|transfer|schedule|on.time|takes? too long|travel.time|time.consum|packed|early|express|bus.only|bus lanes|priority))',
        'action': 'Investigate frequency, crowding, transfer coordination, and travel time by corridor and time of day.'},
    'Transit reach and hours': {
        'definition': 'Bus coverage, destinations, off-campus links, operating hours, weekends, or breaks.',
        'exclude': 'Frequency alone without a coverage or operating-span concern.',
        'pattern': r'(?is)^(?=.*\b(bus(?:es|ses)?|mtd|transit|shuttle|safe.?ride|saferide)\b)(?=.*(?:route|connect|off.campus|outskirts|neighbo|airport|research park|weekend|evening|night|summer|breaks?|holiday|early.morning|hours|ends|stops running|last bus|no bus|further|farther|rural|outside|out of town|south urbana|e14|e-14))',
        'action': 'Assess gaps in residential access, commuter-lot service, evenings, weekends, and airport connections.'},
    'Protected and connected cycling': {
        'definition': 'Continuous, separated, or clearer bike routes and safer transitions between them.',
        'exclude': 'Bike ownership or a generic bike mention without infrastructure context.',
        'pattern': r'(?is)(?:bike|bicycl|cycling|cyclist|biking).{0,110}(?:lane|path|infrastruc|connect|separat|protect|barrier|bollard|curb|network|rack|parking)|(?:lane|path|protect|separat|barrier|bollard).{0,75}(?:bike|bicycl|cycling|cyclist|biking)',
        'action': 'Prioritize continuous protected approaches to campus and safe lane transitions.'},
    'Crossings and motor-vehicle exposure': {
        'definition': 'Crosswalks, turning conflicts, visibility, speeding cars, or fear of being struck by vehicles.',
        'exclude': 'Traffic-rule comments without a specific crossing or vehicle-exposure issue.',
        'pattern': r'(?is)crosswalk|cross.walk|pedestrian.(?:cross|signal)|crossing|cross (?:the |a )?(?:street|road|lincoln)|traffic.calming|speed (?:limit|bump)|speeding|raised.cross|(?:hit|struck|run.over|collisi|near.miss|aggressive).{0,70}(?:car|vehicle|driver|motorist)|(?:car|vehicle|driver|motorist).{0,80}(?:hit|struck|run.over|collisi|near.miss|aggressive|too.fast|speed|not.stop|don.t.stop)|^cars?[.! ]*$',
        'action': 'Audit reported crossings, vehicle speeds, sight lines, and turning conflicts.'},
    'Road-user conduct and enforcement': {
        'definition': 'Distraction, yielding, traffic-rule compliance, education, or enforcement across modes.',
        'exclude': 'Do not infer who is at fault from a road-user mention alone.',
        'pattern': r'(?is)enforc|educat|etiquette|obey|disobey|rules|reckless|pay(?:ing)? attention|not.attentive|distract|cell.?phone|texting|headphones|ear.?buds|wrong.way|stop.sign|traffic.(?:law|signal|sign)|ticket|polic|right.of.way|yield|awareness|red.light|jaywalk',
        'action': 'Combine design changes with education and consistent enforcement across road users.'},
    'Micromobility conflicts': {
        'definition': 'Scooter, e-bike, skateboard, or shared-device safety, speed, storage, or sidewalk conflicts.',
        'exclude': 'A neutral account of using a device without conflict or infrastructure concerns.',
        'pattern': r'(?is)^(?=.*(?:scooter|e.?bike|electric.bike|veo|velo|skateboard|powered.device|motorized|motor.assist|personal.electric|\bpev\b))(?=.*(?:fast|speed|danger|unsafe|reckless|rule|ban|not.allow|sidewalk|pedestrian|abandon|park|storage|store|rack|conflict|hazard|block|building|nuisance|wrong.way|light|visibility))',
        'action': 'Clarify where devices may ride and park; address speed and blocked pedestrian routes.'},
    'Lighting and personal security': {
        'definition': 'Poor lighting, isolation, fear after dark, crime, harassment, or personal safety.',
        'exclude': 'Traffic-signal lights without an illumination or security concern.',
        'pattern': r'(?is)lighting|street.?light|well.lit|poorly.lit|not.well.lit|dark|night|crime|vandal|assault|harass|catcall|alone|isolated|remote.parking|emergency.(?:call|alarm)|blue.phone|safe.?walk|security|safety.presence|police.presence',
        'action': 'Audit illumination and late-hour access between destinations, stops, and parking.'},
    'Maintenance and weather resilience': {
        'definition': 'Uneven pavement, potholes, surface repairs, snow/ice clearance, or weather-related usability.',
        'exclude': 'Weather mentioned only as background without a travel constraint.',
        'pattern': r'(?is)maint(?:ain|enance)|repair|pothole|pot.hole|uneven|unlevel|crack|pavement|resurfac|repaint|worn|snow|ice\b|icy|plow|salt|winter|rain|weather|mud|broken|degrad|vegetation|low.hanging',
        'action': 'Maintain a year-round surface and clearance program for sidewalks and bike routes.'},
    'Accessibility and usable routes': {
        'definition': 'Disability, mobility barriers, ramps, audio signals, benches, or obstructed accessible routes.',
        'exclude': 'Generic use of accessible meaning convenient rather than disability access.',
        'pattern': r'(?is)disab|wheel.?chair|mobility|visually.impaired|audio.walk|audible|ramp|elevator|rest.(?:area|place)|bench|curb.lift|curb.cut|accessib(?:le|ility).{0,65}(?:entrance|route|barrier|sidewalk)|(?:block|obstruct).{0,60}(?:sidewalk|curb|ramp|passage)',
        'action': 'Check complete accessible routes, audio signals, ramps, resting places, and obstructions.'},
    'Parking access and affordability': {
        'definition': 'Parking supply, location, price, permits, waitlists, flexibility, or restrictions.',
        'exclude': 'Bike parking alone; identify the intended mode during review.',
        'pattern': r'(?is)parking.(?:pass|permit|lot|garage|space|spot|rate|cost|fee|option|situation)|(?:more|cheaper|free|expensive|cost|lack.of|enough|limited).{0,30}parking|permit|wait.?list|meter|commuter.lot|e-?14|car.parking|park.my.car',
        'action': 'Examine permit flexibility, waitlists, prices, and commuter-lot connections.'},
    'Car-dependent responsibilities': {
        'definition': 'Caregiving, errands, work tasks, disability, or distance that constrains switching away from a car.',
        'exclude': 'General preference for a car without an expressed practical constraint.',
        'pattern': r'(?is)child|kids?|parent|caregiv|errand|appointment|sick.kid|transport.items|work.details|need.my.car|need.(?:a |the )?car|only.(?:reasonable |feasible )?option|no.(?:other |reasonable )?(?:choice|alternative)|live.(?:far|outside|\d+ miles)|long.distance|commut.{0,25}(?:miles|county|rural)',
        'action': 'Offer alternatives compatible with work, caregiving, distance, and emergency needs.'},
    'Information and wayfinding': {
        'definition': 'Understanding routes, signs, apps, maps, tracking, or orientation to available choices.',
        'exclude': 'Do not label every traffic sign reference as wayfinding.',
        'pattern': r'(?is)wayfinding|mapping|maps?|website|tracking|app\b|information|orientat|learning.curve|confus|understand.{0,40}(?:network|route|system)|signage|signs.{0,25}(?:where|path|lead)',
        'action': 'Improve route guidance, arrival information, signage, and new-user orientation.'}
}

SYNTHESIS = [
    {'title': 'The commute can be harder than the campus trip',
     'meaning': 'Respondents distinguish a walkable, connected campus core from the residential approaches needed to reach it. A good network within campus does not guarantee a practical door-to-door commute.',
     'codes': ['Transit reach and hours','Protected and connected cycling'],
     'tension': 'Some describe convenient bus and bike trips; others describe gaps outside the core. Neither experience should be generalized to every location.',
     'action': 'Study the full journey from residential areas to campus, including transfers and safe walking and biking approaches.',
     'evidence': [('network_comments',776,'If anything, the issue lies with transportation *to* campus and not on it.'),('network_comments',297,'Now I live about seven miles from campus and taking the bus to work is not workable -- takes over an hour to get to work and there are too many transfers.')]},
    {'title': 'Transit is valued, but trust depends on time and coverage',
     'meaning': 'Praise for MTD often coexists with complaints about waiting, crowding, reliability, and hours. These accounts suggest a gap between appreciation for transit and being able to depend on it for a specific trip.',
     'codes': ['Transit operations','Transit reach and hours','Information and wayfinding'],
     'tension': 'Strong positive accounts coexist with negative operational experiences. The comments do not provide a standardized satisfaction score.',
     'action': 'Compare service frequency, crowding, punctuality, and span against the trips and times commenters describe.',
     'evidence': [('network_comments',84,'Overall good. Bus network is strong but should have better off-peak frequencies.'),('network_comments',417,'I think the bus system is wonderful and wish I could take advantage of it more.')]},
    {'title': 'Sharing space creates uncertainty about who goes where',
     'meaning': 'Safety is described as an interaction between design and behavior: disconnected lanes, crossings, and fast-moving devices mix with distraction and inconsistent yielding. Clearer separation can reduce the need to negotiate every encounter.',
     'codes': ['Crossings and motor-vehicle exposure','Road-user conduct and enforcement','Micromobility conflicts','Protected and connected cycling'],
     'tension': 'Some respondents seek fewer cars and protected routes; others emphasize enforcement of pedestrian and cyclist behavior. These are different explanations of risk, not a consensus about fault.',
     'action': 'Combine crossing and lane audits with road-user education, enforcement, and device parking management.',
     'evidence': [('safety_comments',201,'I would feel safer both walking and driving if there was some enforcement on cyclist/scooter behavior.'),('safety_comments',230,'I wish there was at least separation by bollard for most if not all paths, but ideally by planter or even physical curb, and that paths were tucked behind parking to prevent dooring.')]},
    {'title': 'Safety changes with darkness, weather, and route condition',
     'meaning': 'The same route can be acceptable by day but uncomfortable after dark or in winter. Lighting, surface condition, clearance, and late service belong to the usable transportation network.',
     'codes': ['Lighting and personal security','Maintenance and weather resilience','Transit reach and hours'],
     'tension': 'Some explicitly report no concerns during daytime while describing different experiences after dark. General safety ratings can hide those conditions.',
     'action': 'Audit night journeys and coordinate lighting, snow/ice clearance, maintenance, and evening connections.',
     'evidence': [('safety_comments',355,'In some areas of campus, the lighting makes it difficult to navigate as well as cars to see pedestrians, so having more light would be useful.'),('safety_comments',332,'Bike lanes and paths are the last areas to be cleared and sometimes are not cleared before the snow melts.')]},
    {'title': 'Changing modes must fit responsibilities beyond campus',
     'meaning': 'Driving can support caregiving, work tasks, rural commutes, and emergencies. These accounts challenge the assumption that incentives alone can make every trip shift to another mode.',
     'codes': ['Car-dependent responsibilities','Parking access and affordability'],
     'tension': 'Calls to reduce car traffic coexist with requests for more affordable and flexible parking. Both need to be considered in a transition strategy.',
     'action': 'Assess flexible parking and reliable alternatives for caregiving, off-campus work, longer commutes, and emergency travel.',
     'evidence': [('network_comments',327,'However for some folks - single parents with children - a car is the only reasonable option to get to campus.'),('network_comments',417,"For now I need to drive to campus as I need to be able to drive to my child's school.")]},
    {'title': 'A route is only accessible when every link works',
     'meaning': 'Ramps, accessible entrances, audio signals, and unobstructed paths matter together. Infrastructure that exists but requires a long detour or is blocked may still fail to provide a usable trip.',
     'codes': ['Accessibility and usable routes','Maintenance and weather resilience','Micromobility conflicts'],
     'tension': 'A low number of disability-related comments does not imply a low priority. These experiences describe consequences that a population-wide average may obscure.',
     'action': 'Review complete accessible journeys with users, including construction detours and device parking.',
     'evidence': [('safety_comments',601,'I am visually impaired and oftentimes the audio walk signals do not function.'),('network_comments',408,'It creates issues for people with limited mobility and is a trip liability for the university.')]}]

def comment_id(field, text, source_row):
    return hashlib.sha256((field+'\n'+str(source_row)+'\n'+text).encode()).hexdigest()[:20]

def suggested_codes(text):
    return [name for name, rule in CODEBOOK.items() if re.search(rule['pattern'], text)]

def comment_frame(data):
    rows=[]
    for idx,row in data.iterrows():
        for field in ['safety_comments','network_comments']:
            text=row[field]
            if not text: continue
            rows.append({'Comment_ID':comment_id(field,text,int(idx)+2),'Respondent_row':int(idx)+2,
                         'Question':field,'Comment':text,'Role':row.role_group,
                         'Suggested_codes':' | '.join(suggested_codes(text))})
    return pd.DataFrame(rows,columns=['Comment_ID','Respondent_row','Question','Comment','Role','Suggested_codes'])

def apply_review(comments, review):
    result=comments.copy()
    result['Codes']=result.Suggested_codes
    result['Status']='Suggested'
    result['Rationale']=''
    if review is None: return result
    required=['Comment_ID','Codes','Status','Rationale']
    if not set(required).issubset(review.columns):
        raise ValueError('Review CSV must contain Comment_ID, Codes, Status, Rationale.')
    review=review.fillna('')
    if review.Comment_ID.duplicated().any():
        raise ValueError('Review CSV contains duplicate Comment_ID values.')
    for v in review.Codes:
        unknown=set(t.strip() for t in str(v).split('|') if t.strip())-set(CODEBOOK)
        if unknown: raise ValueError('Unknown codes: '+', '.join(sorted(unknown)))
    if not set(review.Status).issubset({'Suggested','AI reviewed','Human reviewed'}):
        raise ValueError('Status must be Suggested, AI reviewed, or Human reviewed.')
    lookup=review.set_index('Comment_ID')
    for col in ['Codes','Status','Rationale']:
        mask=result.Comment_ID.isin(lookup.index)
        result.loc[mask,col]=result.loc[mask,'Comment_ID'].map(lookup[col])
    return result

def thematic_counts(comments):
    # Denominator includes all selected writers, including uncoded replies.
    total=comments.Respondent_row.nunique()
    rows=[]
    for name in CODEBOOK:
        match=comments.Codes.map(lambda s:name in [t.strip() for t in s.split('|')])
        n=comments.loc[match,'Respondent_row'].nunique()
        rows.append({'Code':name,'Writers':n,'Percent of selected writers':100*n/total if total else 0,
                     'Comment responses':int(match.sum()),'Writers denominator':total})
    return pd.DataFrame(rows).sort_values('Writers',ascending=False)

def redact_contact(text):
    text=re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b','[email removed]',text,flags=re.I)
    return re.sub(r'(?<!\w)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b','[phone removed]',text)

def narrative_panel(data, all_data):
    st.header('A strong campus network, with uneven journeys to it')
    st.write('This survey suggests that improving transportation means connecting a dependable commute with a safer campus trip. '
             'The descriptive results show different travel patterns across campus roles; written accounts explain how time, '
             'location, street design, and responsibilities can shape those choices.')
    st.caption('Interpretive story based on this survey, not a causal finding or a representative population estimate. Numbers below follow the sidebar filters.')
    st.subheader('1. Different roles have different commute patterns')
    rows=[]
    for role,g in data.groupby('role_group'):
        n=g['mode'].notna().sum()
        rows.append({'Campus role':role,'Answered':int(n),'Drive alone (%)':100*g['mode'].eq('Drive yourself (arrive/depart alone)').sum()/n if n else 0,
                     'Bus (%)':100*g['mode'].eq('Bus').sum()/n if n else 0,
                     'Walk / personal bicycle (%)':100*g['mode'].isin(['Walk/Roll','Personal bicycle','Personal bike during warm weather']).sum()/n if n else 0})
    table=pd.DataFrame(rows)
    st.dataframe(table.round(1),hide_index=True,width='stretch')
    st.caption('Exact recorded categories are used. Differences describe survey respondents and do not establish why they chose a mode.')
    st.subheader('2. Transit needs to compete on time and dependability')
    barriers=summary(data,'bus_barriers',multi=True)
    useful=barriers[~barriers.Response.str.contains('not applicable|comfortable|n/a',case=False,regex=True)].head(3)
    for _,r in useful.iterrows(): st.write(f"**{r.Response}: {r.Percent:.1f}%** ({int(r.Respondents):,} of {int(r.Answered):,} answering).")
    st.write('Read these alongside the accounts of convenient campus bus trips and difficult trips from some residential locations. Service gaps and praise can coexist in the same response.')
    st.subheader('3. Safer, continuous routes support active travel')
    l,r=st.columns(2)
    for panel,key,label in [(l,'walk_improvements','Walking'),(r,'bike_improvements','Biking')]:
        with panel:
            t=summary(data,key,multi=True).head(2)
            st.markdown(f'**{label}: most selected improvements**')
            for _,v in t.iterrows():st.write(f"{v.Response} — **{v.Percent:.1f}%** ({int(v.Respondents):,}/{int(v.Answered):,}).")
    st.subheader('4. A mode shift needs to work beyond the campus boundary')
    driving=data[data['mode'].eq('Drive yourself (arrive/depart alone)')]
    if len(driving):
        t=summary(driving,'driving_reasons',multi=True)
        t=t[~t.Response.str.contains('do not own|do not drive|not applicable',case=False,regex=True)].head(3)
        st.caption('Reasons below are restricted to respondents whose primary mode is drive alone.')
        for _,v in t.iterrows():st.write(f"{v.Response} — **{v.Percent:.1f}%** ({int(v.Respondents):,}/{int(v.Answered):,}).")
    else:st.caption('No primary drive-alone commuters in this selection.')
    st.write('Written comments describe caregiving, work tasks, parking constraints, and longer-distance commutes. These suggest evaluating dependable alternatives and flexibility alongside incentives.')
    st.subheader('5. Hear the experiences behind the numbers')
    st.write('The thematic analysis tab groups the written accounts into six interpretive themes, with contrasting perspectives, source quotes, and planning questions. '
             'The review tab lets you inspect and correct every provisional code.')
    st.caption('The six theme narratives summarize the source dataset as a whole. Theme counts, evidence lists, and quantitative measures respond to filters.')

def thematic_panel(data, all_data, comments):
    st.header('What the written responses reveal')
    st.write('Six exploratory themes connect experiences with possible planning responses. They were developed by reading selected accounts, '
             'comparing contrasting perspectives, and relating them to the closed-question results. Automated code suggestions cover every nonblank response; '
             'they require contextual review before using frequencies as final findings.')
    st.caption('Narratives are interpretive, dataset-wide synthesis. The code counts and evidence below use the current filters. Quotes are illustrative, not randomly sampled.')
    if comments.empty:
        st.info('No written responses in this selection.');return
    a,b,c=st.columns(3)
    a.metric('Writers',f'{comments.Respondent_row.nunique():,}')
    b.metric('Written responses',f'{len(comments):,}')
    c.metric('Human reviewed',f'{comments.Status.eq("Human reviewed").sum():,}')
    scope=st.radio('Coding evidence',['All coding (provisional)','AI-reviewed excerpts only','Human-reviewed responses only'],horizontal=True)
    scoped=comments
    if scope=='AI-reviewed excerpts only':scoped=comments[comments.Status.eq('AI reviewed')]
    if scope=='Human-reviewed responses only':scoped=comments[comments.Status.eq('Human reviewed')]
    if scoped.empty:
        st.info('No reviewed responses for this choice. Use the coding review tab to review and export assignments.')
    else:
        st.subheader('Descriptive codes supporting the themes')
        counts=thematic_counts(scoped)
        fig=px.bar(counts,x='Writers',y='Code',orientation='h',text='Writers',color_discrete_sequence=['#13294B'],
                   hover_data=['Percent of selected writers','Comment responses','Writers denominator'])
        fig.update_layout(yaxis={'autorange':'reversed','title':None},height=520,xaxis_title='Distinct writers with this code')
        st.plotly_chart(fig,width='stretch')
        st.caption(f'{scoped.Respondent_row.nunique():,} writers form this denominator. Each writer counts once per code across both questions. '
                   'Codes overlap, so totals may exceed the writer count. Short replies, cross-references, and uncoded replies remain in the denominator. '
                   'Provisional codes may capture praise, criticism, or a neutral mention; they are not a sentiment measure.')
        with st.expander('Code counts and CSV export'):
            st.dataframe(counts,hide_index=True,width='stretch')
            st.download_button('Download code counts',counts.to_csv(index=False).encode('utf-8-sig'),'theme_counts.csv','text/csv')
        with st.expander('Compare written-question prompts and campus roles'):
            st.caption('Comparisons use distinct writers within each question or role, rather than the full survey population. They are descriptive and follow the coding evidence choice above.')
            rows=[]
            for field,g in scoped.groupby('Question'):
                for record in thematic_counts(g).to_dict('records'):
                    record['Question']='Safety' if field=='safety_comments' else 'Network'
                    rows.append(record)
            st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
            role_rows=[]
            for role,g in scoped.groupby('Role'):
                for record in thematic_counts(g).to_dict('records'):
                    role_rows.append({'Role':role,'Code':record['Code'],
                                      'Percent':record['Percent of selected writers']})
            role_table=pd.DataFrame(role_rows).pivot(index='Code',columns='Role',values='Percent')
            fig=px.imshow(role_table,aspect='auto',labels={'color':'% of writers'},
                          color_continuous_scale=['#FFFFFF','#13294B'],zmin=0,zmax=100)
            st.plotly_chart(fig,width='stretch')
            st.caption('Each cell is the share of writers in that role with the code. Codes overlap, so rows and columns do not total 100%.')
    for item in SYNTHESIS:
        with st.expander(item['title']):
            st.markdown('**Interpretation**');st.write(item['meaning'])
            st.markdown('**Different perspectives**');st.write(item['tension'])
            st.markdown('**Planning question**');st.write(item['action'])
            st.caption('Related descriptive codes: '+', '.join(item['codes']))
            shown=0
            for field,row,excerpt in item['evidence']:
                if row-2 not in data.index:continue
                source=all_data.loc[row-2,field]
                if source and excerpt in source:
                    st.text('“'+excerpt+'”')
                    st.caption(f'Workbook row {row} · '+('Safety question' if field=='safety_comments' else 'Network question'))
                    shown+=1
            if not shown:st.caption('The curated illustrative quotes are outside the current selection. Explore matching coded responses below.')
    st.subheader('Explore evidence')
    code=st.selectbox('Descriptive code',list(CODEBOOK))
    evidence=comments[comments.Codes.map(lambda s:code in [t.strip() for t in s.split('|')])].copy()
    evidence['Comment']=evidence.Comment.map(redact_contact)
    st.dataframe(evidence[['Respondent_row','Question','Comment','Status']],hide_index=True,width='stretch')
    with st.expander('Thematic codebook and method'):
        st.write('Units: one response per question for coding, one distinct workbook row per writer for writer counts. Multiple codes can be assigned. '
                 'The two questions ask about safety and the overall network, so their prompt differences influence what is mentioned. '
                 'Nonresponse and self-selection limit generalization. No intercoder reliability, saturation, or causal conclusions are claimed. '
                 'AI reviewed means selected full responses were read and assigned codes during dashboard development. Human reviewed requires a user review.')
        st.dataframe(pd.DataFrame([{'Code':k,'Include':v['definition'],'Exclude / review':v['exclude'],'Planning question':v['action'],
                                   'Suggestion rule':v['pattern']} for k,v in CODEBOOK.items()]),hide_index=True,width='stretch')

def review_panel(comments, review):
    st.header('Review the coding')
    st.write('Correct code assignments, record a rationale, and mark each response Human reviewed after reading it. '
             'Separate multiple codes with |. Leave Codes empty to explicitly record that none apply. '
             'Download the review CSV and replace thematic_review.csv in GitHub to retain the changes.')
    question=st.selectbox('Review question',['All','safety_comments','network_comments'])
    status=st.selectbox('Review status',['All','Suggested','AI reviewed','Human reviewed'])
    term=st.text_input('Find text to review')
    selected=comments.copy()
    if question!='All':selected=selected[selected.Question.eq(question)]
    if status!='All':selected=selected[selected.Status.eq(status)]
    if term:selected=selected[selected.Comment.str.contains(term,case=False,regex=False)]
    st.caption(f'{len(selected):,} responses in this review view. All editable codes must match the codebook names exactly.')
    if not selected.empty:
        readable=st.selectbox('Read a full response before coding',selected.index.tolist(),
            format_func=lambda i:f"Row {selected.loc[i,'Respondent_row']} · {selected.loc[i,'Question']} · {selected.loc[i,'Comment'][:75]}")
        st.text(selected.loc[readable,'Comment'])
        st.caption('Current codes: '+(selected.loc[readable,'Codes'] or 'None'))
    columns=['Comment_ID','Respondent_row','Question','Comment','Codes','Status','Rationale']
    edit=st.data_editor(selected[columns],hide_index=True,width='stretch',height=500,
        disabled=['Comment_ID','Respondent_row','Question','Comment'],
        column_config={'Status':st.column_config.SelectboxColumn('Status',options=['Suggested','AI reviewed','Human reviewed'],required=True),
                       'Codes':st.column_config.TextColumn('Codes (separate with |)',width='large'),
                       'Comment':st.column_config.TextColumn('Full comment',width='large')},key='coding_editor')
    with st.expander('Available code names'):
        st.write(' | '.join(CODEBOOK))
    try:
        # Merge edits into a full review file, including records outside the current filters.
        original=review.copy() if review is not None else comments.copy()
        original=original.drop_duplicates('Comment_ID').set_index('Comment_ID')
        updates=edit.set_index('Comment_ID')
        for col in ['Codes','Status','Rationale']:
            original.loc[updates.index,col]=updates[col].fillna('')
        output=original.reset_index()
        apply_review(comments,output)
        st.download_button('Download updated thematic_review.csv',output.to_csv(index=False).encode('utf-8-sig'),
                           'thematic_review.csv','text/csv')
        st.caption('Edits are included in the download. To refresh the thematic charts immediately, upload the downloaded CSV in the sidebar. '
                   'Edits do not automatically write to GitHub.')
    except (ValueError,KeyError) as exc:st.error(f'Correct the review entries before export: {exc}')


def main():
    st.set_page_config(page_title='Illinois Campus Transportation', page_icon='🚍', layout='wide')
    st.markdown("""<style>
    .block-container {padding-top:1.7rem;max-width:1500px}
    .illinois-hero {background:#13294B;color:white;padding:30px 34px;border-top:7px solid #FF5F05;margin-bottom:20px;border-radius:0 0 12px 12px}
    .illinois-hero .eyebrow {font-size:13px;letter-spacing:1.6px;text-transform:uppercase;margin-bottom:12px;color:white}
    .illinois-hero h1 {font-size:40px;line-height:1.1;letter-spacing:-.03em;color:white;margin:0;padding:0}
    .illinois-hero p {font-size:18px;max-width:900px;margin:14px 0 0;color:white}
    [data-testid="stMetric"] {background:#F4F4F4;border-top:4px solid #FF5F05;border-radius:5px;padding:16px}
    h1,h2,h3 {color:#13294B}
    </style>""",unsafe_allow_html=True)
    st.markdown("""<div class="illinois-hero"><div class="eyebrow">University of Illinois Urbana-Champaign</div>
    <h1>How we get here.<br>How we move through campus.</h1>
    <p>Campus transportation survey: connecting commute choices, everyday experiences, and opportunities for improvement.</p></div>""",unsafe_allow_html=True)
    source = Path(__file__).with_name('Campus Transportation Survey raw.xlsx')
    if not source.exists():
        st.error('Place Campus Transportation Survey raw.xlsx beside app.py in the GitHub repository.');st.stop()
    try:
        all_data=load_survey(source)
    except Exception as exc:
        st.error(f'Unable to read the workbook: {exc}');st.stop()
    dates=all_data.date.dropna()
    if len(dates): st.caption(f'Survey period: {dates.min():%B %d, %Y} to {dates.max():%B %d, %Y} · Descriptive results and exploratory thematic analysis')
    review_source=Path(__file__).with_name('thematic_review.csv')
    review_upload=st.sidebar.file_uploader('Load revised thematic coding (optional)',type=['csv'])
    try:
        review=pd.read_csv(review_upload if review_upload is not None else review_source,keep_default_na=False) if (review_upload is not None or review_source.exists()) else None
        full_comments=apply_review(comment_frame(all_data),review)
    except (ValueError, pd.errors.ParserError) as exc:
        st.error(f'Invalid thematic review file: {exc}');st.stop()

    st.sidebar.header('Filters')
    eligible_only = st.sidebar.checkbox('U.S. eligible responses only', value=True)
    data = all_data.loc[all_data.eligible.eq('Yes')].copy() if eligible_only else all_data.copy()
    base_count = len(data)
    filter_base = data.copy()
    for key, label in [('role_group','Campus role'), ('age','Age'), ('mode','Primary commute mode'), ('permit','Parking permit')]:
        options = sorted(filter_base[key].fillna('Missing').unique())
        choices = st.sidebar.multiselect(label, options, default=options, key=f'filter_{key}')
        data = data.loc[data[key].fillna('Missing').isin(choices)]
    st.sidebar.caption('Other / multiple roles combines free-text roles. Empty selections return no records.')
    st.sidebar.radio('Chart measure', ['Percent', 'Respondents'], key='measure')
    if data.empty:
        st.warning('No records match these filters. Select additional filter values to continue.')
        st.stop()

    def chart(key, title, multi=False, ranked_first=False, frame=None):
        frame = data if frame is None else frame
        table = summary(frame, key, multi, ranked_first)
        st.subheader(title)
        if table.empty:
            st.caption('No answers in this selection.')
            return
        n = int(table.Answered.iloc[0])
        measure = st.session_state.measure
        plot = table.copy()
        plot['Label'] = plot.Response.map(lambda s: s if len(s) <= 70 else s[:67] + '…')
        fig = px.bar(plot, x=measure, y='Label', orientation='h', text=measure,
                     hover_data={'Response':True, 'Respondents':True, 'Percent':':.1f','Label':False,'Answered':True},
                     color_discrete_sequence=['#FF5F05'])
        fig.update_traces(texttemplate='%{text:.1f}%' if measure == 'Percent' else '%{text:.0f}', textposition='outside', cliponaxis=False)
        fig.update_layout(height=max(320, len(table)*39+75), yaxis={'autorange':'reversed','title':None},
                          xaxis_title='% of respondents answering' if measure == 'Percent' else 'Respondents',
                          margin=dict(l=5,r=70,t=15,b=35))
        st.plotly_chart(fig, width='stretch')
        st.caption(f'{n:,} respondents answered; {len(frame)-n:,} missing. ' +
                   ('Multiple selections allowed; percentages may exceed 100% in total.' if multi else ''))
        with st.expander('Full labels and chart data'):
            st.dataframe(table, hide_index=True, width='stretch')
            st.download_button('Download chart CSV', table.to_csv(index=False).encode('utf-8-sig'),
                               f'{key}_summary.csv', 'text/csv', key=f'download_{key}_{title}')

    def metric(container, title, value, note):
        container.metric(title, '—' if value is None else f'{value:.1f}%')
        container.caption(note)

    st.caption(f'{len(data):,} selected responses out of {base_count:,} in the chosen eligibility group · '
               f'{len(all_data):,} total workbook records')
    a,b,c,d = st.columns(4)
    a.metric('Selected responses', f'{len(data):,}')
    v,n=rate(data,'mode',lambda s:s=='Drive yourself (arrive/depart alone)')
    metric(b,'Drive alone',v,f'{n:,} answered the commute-mode question')
    v,n=rate(data,'mode',lambda s:s=='Bus')
    metric(c,'Primary mode: bus',v,f'{n:,} answered; exact Bus response')
    v,n=rate(data,'permit',lambda s:s=='Yes')
    metric(d,'Parking permit holders',v,f'{n:,} answered the permit question')

    comments=apply_review(comment_frame(data),review)
    story,overview,commute,barriers,safety,themes,explorer,review_tab = st.tabs([
        'The story','Who responded','Commute patterns','Barriers & improvements',
        'Safety & accessibility','Thematic analysis','All questions','Coding review'])
    with story: narrative_panel(data,all_data)
    with themes: thematic_panel(data,all_data,comments)
    with review_tab: review_panel(comments,full_comments)
    with overview:
        l,r=st.columns(2)
        with l: chart('mode','Primary commute mode')
        with r: chart('role_group','Respondents by campus role')
        st.subheader('Mode by campus role')
        ct=pd.crosstab(data.role_group,data['mode'])
        shares=ct.div(ct.sum(axis=1),axis=0)*100
        fig=px.imshow(shares,labels=dict(x='Primary commute mode',y='Campus role',color='Percent'),
                      aspect='auto',color_continuous_scale=['#FFFFFF','#13294B'])
        st.plotly_chart(fig,width='stretch')
        st.caption('Each row totals 100% among respondents in that role who answered the commute-mode question.')
        with st.expander('Data notes'):
            st.write('Each workbook row is treated as one response. No unique respondent identifier is available, so duplicate people cannot be identified. These are unweighted survey results, not estimates of the whole campus population.')
            st.write('Whitespace is cleaned. Free-text mode answers are retained as recorded. The age label “and older” is retained because its lower bound is not specified. ZIP codes are excluded from the analytical data.')
            st.write('Default inclusion: U.S. eligibility = Yes. Missing answers are excluded from each question denominator. Not applicable answers remain visible unless a chart states otherwise. Numeric values are not trimmed or imputed.')
    with commute:
        l,r=st.columns(2)
        with l:
            chart('commute_time','Commute duration')
            chart('telecommute','Telecommuting frequency')
            chart('supplement','Supplemental commute modes',multi=True)
        with r:
            st.subheader('Distance to campus')
            distances=data.distance.dropna()
            if len(distances):
                st.metric('Median commute distance',f'{distances.median():.1f} miles')
                st.plotly_chart(px.histogram(distances.to_frame(),x='distance',nbins=30,labels={'distance':'Miles'}),width='stretch')
                st.caption(f'{len(distances):,} answers. All reported numeric values are retained.')
            chart('campus_mode','Travel within campus')
            chart('rank','First listed preferred mode',ranked_first=True)
            st.caption('The export contains ordered lists, often with all 10 modes despite “rank up to 5” wording. This chart uses only the first recorded item; it does not assume all items were actively ranked.')
    with barriers:
        question=st.selectbox('Choose a topic',MULTI[1:]+['parking'],format_func=lambda k:{
            'bus_barriers':'Barriers to bus use','incentives':'Programs and incentives','driving_reasons':'Reasons for driving alone',
            'walk_improvements':'Walking improvements','bike_improvements':'Biking improvements','parking':'Parking difficulty'}[k])
        chart(question,QUESTIONS[question],multi=question in MULTI)
        st.caption('Counts reflect recorded selections, including not applicable and free-text options. Reasons for driving are shown for everyone who answered; use the primary mode filter to examine drive-alone commuters.')
    with safety:
        l,r=st.columns(2)
        with l: chart('walk_safety','Safety while walking')
        with r: chart('bike_safety','Safety while biking')
        applicable=data.loc[data.bike_safety.notna() & ~data.bike_safety.eq('Not applicable')]
        v,n=rate(applicable,'bike_safety',lambda s:s.startswith(('Somewhat unsafe','Very unsafe')))
        st.metric('Feel unsafe while biking', '—' if v is None else f'{v:.1f}%')
        st.caption(f'{n:,} applicable biking safety answers; excludes Not applicable and missing.')
        chart('accessibility','Experience with campus accessibility')
        st.caption('The accessibility chart includes “No, I don’t have a disability.” Responses reflect self-reported experience.')
    with explorer:
        available=[k for k in QUESTIONS if k not in ['zip','safety_comments','network_comments','date','rank']]
        q=st.selectbox('Survey question',available,format_func=lambda k:QUESTIONS[k])
        if q in NUMERIC:
            values=data[q].dropna()
            st.dataframe(values.describe().to_frame('Value'),width='stretch')
            if len(values): st.plotly_chart(px.histogram(values.to_frame(),x=q,labels={q:QUESTIONS[q]}),width='stretch')
        else: chart(q,QUESTIONS[q],multi=q in MULTI)
    with st.expander('Question response coverage'):
        coverage=pd.DataFrame({'Question':[QUESTIONS[k] for k in QUESTIONS if k not in ['zip','date']],
            'Answered':[int(data[k].notna().sum()) for k in QUESTIONS if k not in ['zip','date']]})
        coverage['Missing']=len(data)-coverage.Answered
        st.dataframe(coverage,hide_index=True,width='stretch')

if __name__ == '__main__':
    main()

from tomorrowcities.utils import read_zipshp 
import pandas as pd
import uuid
import json
import io
import fiona
import os.path
import numpy as np
import pandas as pd
import geopandas as gpd
import random
from random import sample
from numpy.random import multinomial, randint
from math import ceil
import math
from itertools import repeat, chain
import warnings
warnings.simplefilter(action='ignore')

class DataGenerator:
  def __init__(self, parameter_file, land_use_file):
    self.parameter_file = parameter_file
    self.land_use_file = land_use_file

  def generate(self, seed=42):
    ipfile = self.parameter_file
    random.seed(seed)
    np.random.seed(seed)
    df_nc = pd.read_excel(ipfile,sheet_name=1, header=None)
    ipdf = pd.read_excel(ipfile,sheet_name=2, header=None)
    df1 = pd.read_excel(ipfile,sheet_name=3, header=None)
    df2 = pd.read_excel(ipfile,sheet_name=4, header=None)
    df3 = pd.read_excel(ipfile,sheet_name=5, header=None)


    #%% Extract the nomenclature for load resisting system and land use types
    startmarker = '\['
    startidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(\
                    startmarker,case=False).any(), axis=1)]
        
    endmarker = '\]'
    endidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(\
                    endmarker,case=False).any(), axis=1)]
        
    # Load resisting system types
    lrs_types_temp = df_nc.loc[list(range(startidx.index[0]+1,endidx.index[0]))]
    lrs_types = lrs_types_temp[1].to_numpy().astype(str)
    lrsidx = {}
    count = 0
    for key in lrs_types:
        lrsidx[str(key)] = count
        count+=1
        
    # Landuse Types 
    lut_types_temp = df_nc.loc[list(range(startidx.index[1]+1,endidx.index[1]))]
    lut_types = lut_types_temp[1].astype(str)
    lutidx = {}
    count = 0
    for key in lut_types:
        lutidx[key] = count
        count+=1

    
    #%% Inputs extracted from the excel input file

    opfile_building = 'building_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_household = 'household_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_individual = 'individual_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_landuse =  'landuse_layer_'+str(uuid.uuid4())+'.xlsx'
              
    savefile = ipdf.iloc[8,1]

    # Income types is hardcoded
    avg_income_types =np.array(['lowIncomeA','lowIncomeB','midIncome','highIncome'])

    #Average dwelling area (sqm) wrt income type (44 for LI, 54 for MI, 
    #67 for HI in Tomorrovwille)
    #Range of footprint area fpt_area (sqm) wrt. income type (32-66 for LI,
    # 32-78 for MI and 70-132 for HI in Tomorrowville)                 
    average_dwelling_area = np.array([ipdf.iloc[21,2],ipdf.iloc[21,3],\
                                      ipdf.iloc[21,4],ipdf.iloc[21,5]])

    fpt_area = {'lowIncomeA':np.fromstring(ipdf.iloc[22,2],dtype=float,sep=','),
                'lowIncomeB':np.fromstring(ipdf.iloc[22,3],dtype=float,sep=','),
                'midIncome':np.fromstring(ipdf.iloc[22,4],dtype=float,sep=','),
                'highIncome':np.fromstring(ipdf.iloc[22,5],dtype=float,sep=',')}

    # Storey definition 1- Low rise (LR) 1-4, 2- Mid rise (MR) 5-8,
    # 3- High rise (HR) 9-19
    storey_range = {0:np.fromstring(ipdf.iloc[25,2],dtype=int,sep=','),
                    1:np.fromstring(ipdf.iloc[25,3],dtype=int,sep=','),
                    2:np.fromstring(ipdf.iloc[25,4],dtype=int,sep=',')}

    # Code Compliance Levels (Low, Medium, High): 1 - LC, 2 - MC, 3 - HC
    code_level = np.array(['LC','MC','HC'])

    # Nr of commercial buildings per 1000 individuals
    numb_com = ipdf.iloc[10,1]
    # Nr of industrial buildings per 1000 individuals
    numb_ind = ipdf.iloc[11,1]

    # Area constraints in percentage (AC) for residential and commercial zones. 
    # Total built-up areas in these zones cannot exceed (AC*available area)
    AC_com = ipdf.iloc[14,1] # in percent
    AC_ind = ipdf.iloc[15,1] # in percent

    # Assumption 14 and 15: 1 school per 10000 individuals,
    # 1 hospital per 25000 individuals
    nsch_pi = ipdf.iloc[17,1]
    nhsp_pi = ipdf.iloc[18,1]

    # Unit price for replacement wrt occupancy type and special facility 
    # status of the building
    # Occupancy type is unchangeable, only replacement value is taken from user input
    Unit_price={'Res':ipdf.iloc[28,2],'Com':ipdf.iloc[28,3],'Ind':ipdf.iloc[28,4],
                'ResCom':ipdf.iloc[28,5],'Edu':ipdf.iloc[28,6],'Hea':ipdf.iloc[28,7]}

    #household_building_match = 'footprint' # 'footprint' or 'number_of_units'

    landuse_shp = read_zipshp(self.land_use_file)


    #Calculate area of landuse zones using polygons only if area is not already. 
    # First, convert coordinate system to cartesian
    if 'area' not in landuse_shp.columns:
        landuse_shp_cartesian = landuse_shp.copy()
        landuse_shp_cartesian = landuse_shp_cartesian.to_crs({'init': 'epsg:3857'})
        landuse_shp_cartesian['area']=landuse_shp_cartesian['geometry'].area # m^2
        landuse_shp_cartesian['area']=landuse_shp_cartesian['area']/10**4 # Hectares
        landuse_shp_cartesian = landuse_shp_cartesian.drop(columns=['geometry'])
        landuse = landuse_shp_cartesian.copy()
    else:
        landuse = landuse_shp.copy()
        landuse = landuse.drop(columns=['geometry'])


    #%% Concatenate the dataframes and process the data
    tabledf = pd.concat([df1,df2,df3]).reset_index(drop=True)

    # Define a dictionary containing data distribution tables
    # Table names sorted according to the order in the excel input spreadsheet
    tables_temp = {
        't1':[],'t2':[],'t3':[],'t4':[],'t5':[],'t5a':[],'t6':[],'t9':[],
        't12':[],'t13':[],'t7':[],'t8':[],'t11':[],'t10':[],'t14':[]   
        }
    startmarker = '\['
    startidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(\
                    startmarker,case=False).any(), axis=1)]
        
    endmarker = '\]'
    endidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(\
                    endmarker,case=False).any(), axis=1)]
        

    count=0
    for key in tables_temp:
        #print(startidx.index[count], endidx.index[count])
        tablepart = tabledf.loc[list(range(startidx.index[count]+1,endidx.index[count]))]
        tablepart = tablepart.drop(columns =0 )
        tablepart = tablepart.dropna(axis=1).reset_index(drop=True).values.tolist()
        tables_temp[key].append(tablepart)
        count+=1

    tables = tables_temp

    #If values are zero for industrial and commercial buildings
    if numb_com ==0:
        print('The number of commercial buildings cannot be zero.')
    if numb_ind == 0:
        print('The number of industrial buildings cannot be zero.')


    #%% Function definition: dist2vector
    def dist2vector(d_value, d_number,d_limit,shuffle_or_not):
        # d_value, d_number = vectors of samelength (numpy array)
        # d_limit = single integer which indicates the sum of all values
        #           in d_number. 
        # shuffle_or_not = 'shuffle' will return a randomly shuffled list otherwise
        #     by default or with 'DoNotShuffle' the list will not be shuffled
        # Output: insert_vector is a list
        # Calculate cumulative sum and typecast to integer
        d_number = np.cumsum(d_number).astype('int32')
        d_number[-1] = d_limit #To prevent array broadcast mismatch
        d_number_temp = np.insert(d_number,0,0)
        d_number_round = np.diff(d_number_temp)
        insert_vector_df= pd.DataFrame(np.nan,index=range(d_number[-1]),columns=['iv'])
        a=0
        icount= 0
        for value in d_value:
            b = d_number[icount]  
            subvector = [str(value)]*d_number_round[icount]
            insert_vector_df.loc[range(a,b),'iv'] = subvector
            a = b   
            icount+=1
            
        insert_vector = insert_vector_df['iv'].values.tolist() 
        if shuffle_or_not == 'shuffle':
            random.shuffle(insert_vector)

        return insert_vector 

    #%% The data generation process begins here____________________________________

    #%% Step 1: Calculate maximum population (nPeople)
    nPeople = round(landuse['densityCap']*landuse['area']-landuse['population'])
    nPeople[nPeople<0]=0

    #%% Step 2: Calculate the number of households (nHouse), hhID
    # Assumption 1: Household size distribution is same for different income types
    # Question: How to ensure that there are no NaNs while assigning zone type?

    # Convert Table 1 to numpy array
    t1_list = tables['t1'][0]
    # No. of individuals
    t1_l1 = np.array(t1_list[0], dtype=int) 
    t1_l2 = np.array(t1_list[1], dtype=float) # Probabilities

    # Compute the probability of X number of people living in a household 
    household_prop = t1_l2/sum(t1_l2) 
    # Total number of households for all zones
    nHouse_all = round(nPeople/(sum(household_prop*t1_l1)))
    nHouse_all = nHouse_all.astype('int32')
    nHouse = nHouse_all[nHouse_all>0] # Exclude zones with zero households
    nHouseidx = nHouse.index
    #Preallocate a dataframe with nan to hold the household layer
    household_df = pd.DataFrame(np.nan, index = range(sum(nHouse)),
                                columns=['bldID','hhID','income','nIND','CommFacID',
                                        'income_numb','zoneType','zoneID',
                                        'approxFootprint'])
    #Calculate a list of cumulative sum of nHouse
    nHouse_cuml = np.cumsum(nHouse)
    
    #  Assign household id (hhID) 
    a = 0
    for i in nHouseidx:
        b =  nHouse_cuml[i]
        household_df.loc[range(a,b),'hhID'] = range(a+1,b+1) # First hhID index =1
        household_df.loc[range(a,b),'zoneID'] = landuse.loc[i,'zoneID']
        household_df.loc[range(a,b),'zoneType'] = landuse.loc[i,'avgIncome']
        a = b

    del a,b
    household_df['hhID'] = household_df['hhID'].astype(int)

        
    #%% Step 3: Identify the household size and assign "nInd" values to each household
    a_g = 0
    for i in nHouseidx:
        b_g = nHouse_cuml[i]
        # Find Total of every different nInd number for households
        household_num = nHouse[i] * household_prop
        # Round the household numbers for various numbers of individuals 
        # without exceeding total household number
        cumsum_household_num = np.round_(np.cumsum(household_num)).astype('int32')
        cumsum_household_num_diff = np.diff(cumsum_household_num)
        first_val = nHouse[i] - sum(cumsum_household_num_diff)
        household_num_round = np.insert(cumsum_household_num_diff,0,first_val)
        
        #Generate a column vector     
        d_value = t1_l1
        d_number = cumsum_household_num
        insert_vector = np.ones(d_number[-1])
        a, count =0, 0
        for value in d_value:
            b = d_number[count]
            #This works for numbers but not for strings
            subvector = np.empty(household_num_round[count]) #
            subvector.fill(value) #
            insert_vector[a:b] = subvector #
            a = b
            count+=1
        del a,b  
        insert_vector = np.random.permutation(insert_vector)
        
        household_df.loc[range(a_g,b_g), 'nIND'] = insert_vector 
        a_g = b_g

    del a_g, b_g, count,insert_vector,subvector

    household_df['nIND'] = household_df['nIND'].astype(int)


    #%% Step 4: Identify and assign income type of the households
    # Table 2 states the % of various income groups in different income zones
    # Convert Table 2 to numpy array
    # for row in range((len(tables['t2'][0]))):
    #     tables['t2'][0][row]=np.fromstring(tables['t2'][0][row],dtype=float,sep=',') 

    t2 = np.array(tables['t2'][0])
    # avg_income_types = ['lowIncomeA','lowIncomeB','midIncome','highIncome']

    count = 0

    for inc in avg_income_types:
        #Find indices corresponding to a zone type
        itidx = household_df['zoneType'] == inc
        if sum(itidx) ==0: #i.e. this income zone doesn't exist in the landuse data
            continue
        income_entries = t2[count]*sum(itidx)    
        d_limit = sum(itidx) # Size of array to match after rounding off
        d_value = avg_income_types[income_entries!=0]
        d_number = income_entries[income_entries!=0] #ip
        
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle') 
        count+=1    
        household_df.loc[itidx, 'income'] = insert_vector 

    del count,insert_vector

        

    #%% Step 5: Identify and assign a unique ID for each  individual

    #Asumption 2: Gender distribution is same for different income types 

    #Preallocate a dataframe with nan to hold the individual layer
    nindiv = int(sum(household_df['nIND'])) # Total number of individuals
    individual_df = pd.DataFrame(np.nan, index = range(nindiv),
                            columns=['hhID', 'indivID', 'gender', 'age','head',
                                    'eduAttStat','indivFacID_1','indivFacID_2',
                                    'schoolEnrollment','labourForce','employed'])
    individual_df.loc[range(nindiv),'indivID'] = [range(1,nindiv+1)]
    individual_df['indivID'].astype('int')

    #%% Step 6: Identify and assign gender for each individual
    # Convert the gender distribution table 3 to numpy array
    tables['t3'][0] = np.array(tables['t3'][0][0],dtype=float) 
    female_p = tables['t3'][0][0]
    male_p = 1-female_p
    gender_value = np.array([1,2], dtype=int) # 1=Female, 2=Male
    gender_number = np.array([female_p, male_p])*nindiv

    d_limit = nindiv # Size of array to match after rounding off
    d_value = gender_value
    d_number = gender_number 

    insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
    individual_df.loc[range(nindiv),'gender'] = insert_vector
    individual_df['gender'] = individual_df['gender'].astype('int')

    #%% Step 7: Identify and assign age for each individual
    #Assumption 3: Age profile is same for different income types
    #Convert the age profile wrt gender distribution table 4 to numpy array
    ageprofile_value = np.array([1,2,3,4,5,6,7,8,9,10], dtype=int)
    t4_l1_f = np.array(tables['t4'][0][0], dtype=float) #For female
    t4_l2_m = np.array(tables['t4'][0][1], dtype=float) #For male
    t4 = np.array([t4_l1_f, t4_l2_m])

    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]    
        d_limit = sum(gidx)
        d_value = ageprofile_value
        d_number = t4[i]*sum(gidx)    
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
        individual_df.loc[gidx,'age'] = insert_vector

    individual_df['age'] = individual_df['age'].astype(int) 


    #%% Step 8: Identify and assign education attainment status for each individual

    # Assumption 4: Education Attainment status is same for different income types 
    # Education Attainment Status (Meta Data)
    # 1 - Only literate
    # 2 - Primary school
    # 3 - Elementary sch.
    # 4 - High school
    # 5 - University and above
    #Convert the educational status distribution table 5 to numpy array
    education_value = np.array([1,2,3,4,5], dtype=int)
    t5_l1_f = np.array(tables['t5'][0][0], dtype=float) #For female
    t5_l2_m = np.array(tables['t5'][0][1], dtype=float) #For male
    t5 = np.array([t5_l1_f, t5_l2_m])

    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]    
        d_limit = sum(gidx)
        d_value = education_value
        d_number = t5[i]*sum(gidx)    
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
        individual_df.loc[gidx,'eduAttStat'] = insert_vector

    individual_df['eduAttStat'] = individual_df['eduAttStat'].astype(int)

    #%% Step 9: Identify and assign the head of household to corresponding hhID

    # Assumption 5: Head of household is dependent on gender
    # Assumption 6: Only (age>20) can be head of households
    #Convert the head of houseold distribution table 6 to numpy array
    tables['t6'][0] = np.array(tables['t6'][0][0],dtype=float) 
    female_hh = tables['t6'][0][0]
    male_hh = 1-female_hh

    # Calculate the number of household heads by gender
    hh_number= np.array([female_hh, male_hh])*sum(nHouse)
    hh_number= hh_number.astype(int)
    hh_number[0] = sum(nHouse) - hh_number[1]

    for i in range(len(gender_value)): #Assign female and male candidates
        gaidx= (individual_df['gender'] == gender_value[i]) & \
                (individual_df['age']>4) # '>4' denotes above age group '18-20'    
        #Index of household head candidates in individual_df
        hh_candidate_idx =  list(individual_df.loc[gaidx,'gender'].index)            
        # Take a random permutation sample to obtain household head indices from 
        # the index of possible household candidates in individual_df
        ga_hh_idx = random.sample(hh_candidate_idx, hh_number[i])                                         
        #print('gaidx=',sum(gaidx), 'ga_hh_idx', len(ga_hh_idx))
        
        individual_df.loc[ga_hh_idx,'head'] = 1
        


    # 1= household head, 2= household members other than the head    
    individual_df.loc[individual_df['head'] != 1,'head'] =0

    #Assign household ID (hhID) randomly
    hhid_temp = household_df['hhID'].tolist()
    random.shuffle(hhid_temp)
    individual_df.loc[individual_df['head'] == 1,'hhID'] = hhid_temp

    #%% Step 10: Identify and assign the household that each individual belongs to
    # In relation with Assumption 6, no individuals under 20 years of age can live
    # alone in an household
    individual_df_temp = individual_df[individual_df['head']==0]
    individual_df_temp_idx = list(individual_df_temp.index)
    #hhidlist = household_df['hhID'].tolist()
    for i in range(1,len(t1_l1)): #Loop through household numbers >1
        hh_nind = t1_l1[i] # Number of individuals in households
        # Find hhID corresponding to household numbers
        hh_df_idx = household_df['nIND']== hh_nind
        hhidx = household_df.loc[hh_df_idx,'hhID'].tolist()
        #Random shuffle hhidx here
        amph = hh_nind -1 # additional member per household
        for j in range(amph):
            # Randomly select len(hhidx) number of indices from individual_df_temp_idx
            idtidx = random.sample(individual_df_temp_idx, len(hhidx))
            individual_df.loc[idtidx,'hhID'] = hhidx
            #Remove idtidx before next iteration
            individual_df_temp = individual_df_temp.drop(index=idtidx)
            individual_df_temp_idx = list(individual_df_temp.index)
            
    individual_df['hhID'] = individual_df['hhID'].astype(int)

    #%% Step 10a: Identify school enrollment for each individual
    # Final output 0 = not enrolled in school, 1 = enrolled in school 
    # Assumption 16: Schooling age limits- AP2 and AP3 ( 5 to 18 years old) 
    # can go to school
    # Convert distribution table 5a to numpy array
    # Table 5a contains school enrollment probability
    for row in range((len(tables['t5a'][0]))):
        tables['t5a'][0][row]=np.array(tables['t5a'][0][row],dtype=float) 
    t5a = np.array(tables['t5a'][0]) # Table 5a
    # Find individuals with age between 5-18 (these are students)
    # Also find individual Id of students and household Id of students
    agemask = (individual_df['age'] == 2) | (individual_df['age']==3) 
    school_df = pd.DataFrame(np.nan, index = range(sum(agemask)),
                    columns=['indivID','hhID','eduAttStatH','income','enrollment'])
    school_df_idx = individual_df.loc[agemask,'indivID'].index
    school_df.set_index(school_df_idx, inplace=True)
    school_df['indivID'] = individual_df.loc[agemask,'indivID']
    school_df['hhID'] = individual_df.loc[agemask,'hhID']
    # Then, pick a slice of individual_df corresponding to the household a student
    # belongs to. From there, Pick eduAtt status of head of household. To expedite
    # computation, dataframe columns have been converted to list
    school_df_hhid_list = list(school_df['hhID'])
    temp_df = individual_df[individual_df['hhID'].isin(school_df_hhid_list)]
    head4school_df = temp_df[temp_df['head'] == 1]
    head4school_df_hhID_list = list(head4school_df['hhID'])
    head4school_df_edus_list = list(head4school_df['eduAttStat'])
    school_df_edu_list = np.ones(len(school_df_hhid_list))*np.nan

    # Label 'lowIncomeA' and 'lowIncomeB' = 1, 'midIncome' =2, 'highIncome' =3
    household_df_hhid_list = list(household_df['hhID'])
    #Use .copy() to avoid SettingwithCopyWarning
    income4school_df=household_df[household_df['hhID'].\
                                  isin(school_df_hhid_list)].copy()
    li_mask = (income4school_df['income'] == avg_income_types[0]) |\
              (income4school_df['income'] == avg_income_types[1]) 
    lm_mask = income4school_df['income'] == avg_income_types[2]
    lh_mask = income4school_df['income'] == avg_income_types[3]
    income4school_df.loc[li_mask,'income'] = 1
    income4school_df.loc[lm_mask,'income'] = 2
    income4school_df.loc[lh_mask,'income'] = 3
    income4school_df_income_list = list(income4school_df['income'])
    income4school_df_hhID_list = list(income4school_df['hhID'])
    school_df_income_list = np.ones(len(school_df_hhid_list))*np.nan

    count=0
    # NOTE: If the operation inside this for loop can be replaced with indexing
    # operation the computation time for this code can be further reduced.
    for hhid in school_df_hhid_list:
        #assign education attained by head of household to school_df
        hhid_temp = [i for i, value in enumerate(head4school_df_hhID_list)\
                    if value == hhid ]
        school_df_edu_list[count] = head4school_df_edus_list[hhid_temp[0]]
        #assign income type of household to school_df
        hhid_temp2 = [i for i, value in enumerate(income4school_df_hhID_list)\
                    if value == hhid ]
        school_df_income_list[count] = income4school_df_income_list[hhid_temp[0]]
        count+=1
        
    school_df.loc[school_df.index, 'eduAttStatH'] = school_df_edu_list 
    school_df['eduAttStatH'] = school_df['eduAttStatH'].astype(int)
    school_df['income'] = school_df_income_list
    school_df['income'] = school_df['income'].astype(int)
      
    #assign school enrollment (1 = enrolled, 0 = not enrolled)
    for incomeclass in range(1,4): # Income class 1,2,3
        for head_eduAttStat in range(1,6): # Education attainment category 1 to 5
            enrmask = (school_df['income'] == incomeclass) &\
                      (school_df['eduAttStatH'] == head_eduAttStat)
            no_of_pstudents = sum(enrmask) # Number of potential students
            if no_of_pstudents ==0: #continue if no students exist for given case
                continue
            i,j = incomeclass-1, head_eduAttStat-1 # indices to access table 5a
            d_limit = no_of_pstudents # Size of array to match after rounding off
            d_value = [1,0] #1= enrolled, 0 = not enrolled
            d_number = np.array([t5a[i,j], 1-t5a[i,j]])*no_of_pstudents        
            insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle') 
            school_df.loc[enrmask,'enrollment'] = insert_vector
            
    school_df['enrollment']= school_df['enrollment'].astype(int)
    # Substitute the enrollment status back to individual_df dataframe
    individual_df.loc[school_df.index,'schoolEnrollment']=  school_df['enrollment']   


    #%% Step 11: Identify approximate total residential building area needed
    # (approxDwellingAreaNeeded_sqm) 
    # Assumption 7a: Average dwelling area (sqm) wrt income type (44 for LI, 
    # 54 for MI, 67 for HI in Tomorrovwille)
    # The output is stored in the column 'totalbldarea_res' in landuse_res_df,
    # which represents the total buildable area

    #Sub dataframe of landuse type containing only residential areas
    landuse_res_df = landuse.loc[nHouse.index].copy()
    landuse_res_df.loc[nHouse.index,'nHousehold'] = nHouse
    hh_temp_df = household_df.copy()

    for i in range(0,len(avg_income_types)):
        hh_temp_df['income'] = hh_temp_df['income'].replace(avg_income_types[i],\
                                                        average_dwelling_area[i])
    for index in landuse_res_df.index: # Loop through each residential zone
        zoneID = landuse_res_df['zoneID'][index]
        sum_part = hh_temp_df.loc[hh_temp_df['zoneID']==zoneID,'income'].sum()
        landuse_res_df.loc[index, 'approxDwellingAreaNeeded_sqm'] = sum_part
        
    # Zones where no households live i.e. potential commercial or industrial zones    
    noHH = nHouse_all[nHouse_all<=0].index
    landuse_ic_df = landuse.loc[noHH].copy()
    landuse_ic_df['area'] = landuse_ic_df['area']*10000 # Convert hectare to sq m
        
    #%% Note on Land use types (LUT), load resisting system (LRS) and storey height
    # Land Use Type 
    # 1 - 'AGRICULTURE'                     
    # 2 - 'CITY CENTER'                     
    # 3 - 'COMMERCIAL AND RESIDENTIAL'      
    # 4 - 'HISTORICAL PRESERVATION AREA'    
    # 5 - 'INDUSTRY'                        
    # 6 - 'NEW DEVELOPMENT'                 
    # 7 - 'NEW PLANNING'                    
    # 8 - 'RECREATION AREA'                 
    # 9 - 'RESIDENTIAL (GATED NEIGHBORHOOD)'
    # 10- 'RESIDENTIAL (HIGH DENSITY)'      
    # 11- 'RESIDENTIAL (LOW DENSITY)'       
    # 12- 'RESIDENTIAL (MODERATE DENSITY)'

    # Storey definition:
    # 1 - Low rise (LR) 1-4
    # 2 - Mid rise (MR) 5-8
    # 3 - High rise (HR) 9-19

    # LRS Types
    # 1 - BrCfl: brick and cement with flexible floor;		
    # 2 - BrCri: brick and cement with rigid floor;		
    # 3 - BrM: brick and mud		
    # 4 - Adb: Adobe		
    # 5 - RCi : Reinforced Concrete infill

    # Code Compliance Levels (Low, Medium, High): 1 - LC, 2 - MC, 3 - HC

    # Occupancy types: Residential (Res), Industrial (Ind), Commercial (Com)
    # Residential and commercial mixed (ResCom)

    #%% Steps 12,13,14,15: 
    #    Identify number of residential buildings and generate building layer 
    # Asumption 7: Range of footprint area (sqm) wrt. Income type (32-66 for LI, 
    # 32-78 for MI and 70-132 for HI in Tomorrowville)

    # Table 7 contains Number of storeys distribution for various LRS and LUT
    # Table 11 contains code compliance distribution for various LRS and LUT
    t7= tables['t7'][0]
    t11 = tables['t11'][0]

    # Convert Table 8 to numpy array
    # Table8 contains LRS distribution with respect to various LUT
    for row in range((len(tables['t8'][0]))):
        tables['t8'][0][row]=np.array(tables['t8'][0][row],dtype=float) 
    t8 = np.array(tables['t8'][0]) # Table 8

    # Determine the number of buildings in each zone based on average income class 
    # building footprint range for each landuse zone and Tables 7 and 8
    no_of_resbldg = 0 # Total residential buildings in all zones
    footprint_base_sum = 0 # footprint at base, not multiplied by storeys
    footprint_base_L,storey_L,lrs_L,zoneid_L,codelevel_L = [],[],[],[],[]

    for i in landuse_res_df.index: #Loop through zones   
        zoneid = landuse_res_df['zoneID'][i]
        #totalbldarea_res = landuse_res_df['totalbldarea_res'][i]
        #totalbldarea_res is the total residential area that needs to be built
        totalbldarea_res = landuse_res_df.loc[i,'approxDwellingAreaNeeded_sqm']
        avgincome = landuse_res_df['avgIncome'][i]
        lut_zone = landuse_res_df['LuF'][i]
        fpt_range = fpt_area[avgincome]
        # Generate a vector of footprints such that sum of all the footprints in
        # lenmax equals maximum possible length of vector of building footprints
        lenmax = int(totalbldarea_res/np.min(fpt_range))
        footprints_temp = np.random.uniform(np.min(fpt_range),\
                                        np.max(fpt_range), size=(lenmax,1))
        footprints_temp = footprints_temp.reshape(len(footprints_temp),)
        # Select LRS using multinomial distribution and Table 8
        lrs_number=multinomial(len(footprints_temp), t8[lutidx[lut_zone]],size=1) 
        lrs_vector=np.array(dist2vector(lrs_types,lrs_number,\
                                                np.sum(lrs_number),'shuffle')) 

        # Select storeys in a zone for various LRS using multinomial distribution
        #storey_vector = np.array([],dtype=int)
        storey_vector = np.array(np.zeros(len(lrs_vector),dtype=int)) #must be assigned after loop
        for lrs in lrs_types: # Loop through LRS types in a zone
            t7row = t7[lutidx[lut_zone]] #Extract row for LUT
            #Extract storey distribution in row for LRS
            t7dist = np.fromstring(t7row[lrsidx[lrs]],dtype=float, sep=',')
            lrs_pos = lrs_vector==lrs
            storey_number = multinomial(sum(lrs_pos),t7dist,size=1)
            storey_vector_part = np.array([],dtype=int)
            for idx,st_range in storey_range.items(): #Loop through storey classes
                sv_temp = \
                    randint(st_range[0],st_range[1]+1,storey_number[0][idx])
                storey_vector_part = \
                    np.concatenate((storey_vector_part,sv_temp),axis =0)
            # Need to shuffle storey_vector before multiplying and deleting
            #extra values, otherwise 100% of storeys will be low rise, resulting in 
            #larger number of buildings        
            np.random.shuffle(storey_vector_part)         
            storey_vector[lrs_pos] =storey_vector_part
        # Select code compliance level for various LRS using multinomial dist
        cc_vector = [] # code compliance vector for a zone
        for lrs in lrs_types: # for each LRS in a zone
            t11row = t11[lutidx[lut_zone]]
            t11dist = np.fromstring(t11row[lrsidx[lrs]],dtype=float, sep=',')
            lrs_pos = lrs_vector==lrs
            cc_number = multinomial(sum(lrs_pos),t11dist,size=1)
            cc_part = dist2vector(code_level, cc_number,sum(lrs_pos),'shuffle')
            cc_vector += cc_part
        random.shuffle(cc_vector)
        
        #If it is necessary to equalize number of storeys = number of households
        storey_vector_cs = np.cumsum(storey_vector)
        stmask = storey_vector_cs <= landuse_res_df.loc[i,'nHousehold']
        stlimit_idx = np.max(np.where(stmask))+1
        stlimit_idx_range = range(stlimit_idx+1,len(footprints_temp))
        
        #If it is necessary to equalize required footprint = provided footprint
        footprints_base = footprints_temp   #Footprints without storey  
        dwellingArea_temp= footprints_temp*storey_vector
        dwellingArea_temp_cs = np.cumsum(dwellingArea_temp)
        #OPTIONAL:Here, introduce a method to match total buildable area (dwelling)
        fpmask = dwellingArea_temp_cs <= totalbldarea_res
        #Indices of footprints whose sum <= dwelling area needed in a zone
        # '+ 1' provides slightly more dwelling area than needed
        footprints_idx = np.max(np.where(fpmask)) + 1 
        
        # Delete additional entries in the vectors for footprint, lrs and storeys
        # which do not fit into total buildable area
        #ftrange = range(footprints_idx+1,len(dwellingArea_temp))
        ftrange = stlimit_idx_range
        
        dwellingArea = np.delete(dwellingArea_temp,ftrange)
        footprints_base = np.delete(footprints_base,ftrange)
        lrs_vector_final = np.delete(lrs_vector,ftrange)
        storey_vector_final = np.delete(storey_vector,ftrange)
        cc_vector = np.array(cc_vector)
        cc_vector_final = np.delete(cc_vector,ftrange)
        no_of_resbldg += len(dwellingArea) 
        
        #footprint_base_sum+=np.sum(footprints_base)    
        # Store the vectors in lists for substitution in dataframe 
        footprint_base_L +=  list(footprints_base)
        storey_L += list(storey_vector_final)
        lrs_L += list(lrs_vector_final)
        zoneid_L += [zoneid]*len(dwellingArea) 
        codelevel_L += list(cc_vector_final)
        
        landuse_res_df.loc[i,'footprint_sqm'] = np.sum(footprints_base)
        landuse_res_df.loc[i,'dwellingAreaProvided_sqm'] = np.sum(dwellingArea)
        
        landuse_res_df.loc[i, 'Storey_units'] = sum(storey_vector_final)
        #'No_of_res_buildings' denotes total residential + ResCom buildings
        landuse_res_df.loc[i, 'No_of_res_buildings'] = len(footprints_base)
        # Check distribution after deletion (for debugging) by counting LR
        #print(sum(storey_vector_final<5)/len(storey_vector_final))

    # landuse_res_df['area'] denotes the total buildable area   
    landuse_res_df['area'] *= 10000 # Convert hectares to sq m, 1ha =10^4 sqm

    # landuse_res_df['builtArea_percent'] denotes the percentage of total 
    # buildable area that needs to be built to accomodate the projected population
    landuse_res_df['builtArea_percent'] =\
        landuse_res_df['footprint_sqm']/landuse_res_df['area']*100

    #ADD HERE : EXCEPTION HANDLING for built area exceeding available area

    #print(no_of_resbldg) 

    #ADD: Check if calculated footprint exceeds total buildable area (landuse.area)  

    #Create and populate the building layer, with unassigned values as NaN
    resbld_df = pd.DataFrame(np.nan, index = range(0, no_of_resbldg),
                            columns=['zoneID', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'OccBld','lrstype','CodeLevel',
                                      'nstoreys'])
    resbld_range = range(0,no_of_resbldg)
    #resbld_df.loc[resbld_range,'bldID'] = list(range(1,no_of_resbldg+1))
    resbld_df.loc[resbld_range,'zoneID'] = zoneid_L
    resbld_df['zoneID'] = resbld_df['zoneID'].astype('int')
    resbld_df.loc[resbld_range,'OccBld'] = 'Res'
    resbld_df.loc[resbld_range,'specialFac'] = 0
    resbld_df.loc[resbld_range,'fptarea'] = footprint_base_L
    resbld_df.loc[resbld_range,'nstoreys'] = storey_L
    resbld_df.loc[resbld_range,'lrstype'] = lrs_L
    resbld_df.loc[resbld_range,'CodeLevel'] = codelevel_L


    #%% Assign zoneIDs and building IDs for Res and ResCom
    # Assign 'ResCom' status based on Table 9
    # Assumption: Total residential buildings = Res + ResCom
    # Convert Table 9 to numpy array
    # Table 9 contains occupancy type with respect to various LUT
    # Occupancy types: Residential (Res), Industrial (Ind), Commercial (Com)
    # Residential and commercial mixed (ResCom)
    for row in range((len(tables['t9'][0]))):
        tables['t9'][0][row]=np.array(tables['t9'][0][row],dtype=float) 
    t9 = np.array(tables['t9'][0]) # Table 9

    #available_LUT = list(set(landuse_res_df['LuF']))
    available_zoneID = list(set(resbld_df['zoneID']))
    for zoneID in available_zoneID: #Loop through zones
        zonemask = resbld_df['zoneID'] == zoneID
        zone_idx = list(zonemask.index.values[zonemask])
        lutlrdidx=landuse_res_df[landuse_res_df['zoneID']==zoneID].index.values[0]
        #Occupancy type distribution for a zone
        occtypedist = t9[lutidx[ landuse_res_df['LuF'][lutlrdidx]]]
        no_of_resbld = sum(zonemask) # Number of residential buildings in a zone
        if occtypedist[3] !=0: # if mixed residential+commercial buildings exist
            # nrc = number of mixed res+com buildings in a zone
            nrc = int(occtypedist[3]/occtypedist[0]*no_of_resbld)
        else: # if only residential buildings exist
            continue
        nrc_idx = sample(zone_idx,nrc)
        resbld_df.loc[nrc_idx,'OccBld'] = 'ResCom'

    #Assign building Ids for res and rescom buildings
    lenresbld = len(resbld_df)
    resbld_df.loc[range(0,lenresbld),'bldID'] = list(range(1,lenresbld+1))
    resbld_df['bldID'] = resbld_df['bldID'].astype('int')


    #%% STEP16: Identify and assign number of households and residents for each 
    #residential building
    #Assign nHouse, residents. All the households and residents must be assigned
    #to this layer.

    dwellings_str=dist2vector(resbld_df['bldID'],np.array(storey_L),\
                                        np.sum(np.array(storey_L)),'DoNotShuffle')
    dwellings = list(map(int,dwellings_str))
    #dwellings.sort()
    dwellings_selected = dwellings[0:len(household_df)]
    random.shuffle(dwellings_selected)
    #Assign building IDs to all households
    household_df.loc[:,'bldID'] = dwellings_selected

    # The number of residential  buildings are slightly more than that needed by 
    # the total population. After the IDs are sorted, some of the buildings towards
    # the end of the list will receive no population, and will be deleted from the 
    # building dataframe.
    # QUESTION: What will happen if the household_df zoneType and ZoneIDs are 
    # modified to inherit the zoneType and zoneIDs of the building they are
    # assigned to at this step? ANSWER: It could conflict with Table 2, but it 
    # eliminates the inconsistency between building income zone and income level
    # of its inhabitants.

    # Assign number of households and residents to residential buildings resbld_df
    # This loop must be optimized for speed
    count =0
    for bldid in resbld_df['bldID']:
        bldidmask = household_df['bldID'] == bldid
        resbld_df.loc[count,'nHouse'] = sum(bldidmask)
        resbld_df.loc[count,'residents'] =sum(household_df['nIND'][bldidmask])
        count+=1
        
    # Remove rows in resbld_df which contains no residents
    to_del = resbld_df['nHouse']  ==0
    resbld_df = resbld_df.drop(index=resbld_df.index[to_del])    


    #%% Step 17,18: Identify and generate commercial and industrial buildings
    # No household or individual lives in com, ind, hosp, sch zones
    # Assumption 10 and 11: Assume a certain number of commercial and industrial
    # buildings per 1000 individuals 
        
    # No commercial and industrial buildings in:recreational areas,agriculture,
    # residential (gated neighbourhood), residential (low-density)
    # But com an ind build can occur in any zone where permitted by table 9
    ncom = round(nindiv/1000*numb_com)
    nind = round(nindiv/1000*numb_ind)
    nci = np.array([ncom,nind])
    occbld_label = ['Com','Ind']
    nci_cs = np.cumsum(nci)
    indcom_df = pd.DataFrame(np.nan, index = range(0, ncom+nind),
                            columns=['zoneID', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'lut_number','OccBld','lrstype','CodeLevel',
                                      'nstoreys'])

    t10= tables['t10'][0] # Extract Table 10
    a = 0
    for i in range(0,len(nci)): # First commercial, then industrial
        attr = t10[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        fpt_ic = np.fromstring(attr[0], dtype=float, sep=',')
        nstorey_ic = np.fromstring(attr[1], dtype=int, sep=',')
        codelevel_ic = np.fromstring(attr[2], dtype=float, sep=',')
        lrs_ic = np.fromstring(attr[3], dtype=float, sep=',')
        range_ic = range(a,nci_cs[i])
        a = nci_cs[i]
        # Generate footprints
        indcom_df.loc[range_ic,'fptarea'] = np.random.uniform(\
                np.min(fpt_ic),np.max(fpt_ic), size=(nci[i],1)).reshape(nci[i],)
        # Generate number of storeys
        indcom_df.loc[range_ic,'nstoreys'] =randint(np.min(nstorey_ic),\
                  np.max(nstorey_ic)+1,size=(nci[i],1)).reshape(nci[i],)
        # Generate code compliance
        cc_number_ic = multinomial(nci[i],codelevel_ic,size=1)
        indcom_df.loc[range_ic,'CodeLevel'] =\
                          dist2vector(code_level, cc_number_ic,nci[i],'shuffle')
        # Generate LRS
        lrs_number_ic = multinomial(nci[i],lrs_ic,size=1)
        indcom_df.loc[range_ic,'lrstype'] =\
                          dist2vector(lrs_types,lrs_number_ic,nci[i],'shuffle')
        indcom_df.loc[range_ic,'OccBld']= occbld_label[i]                     

    # Assign number of households, Residents, special facility label
    range_all_ic = range(0,len(indcom_df))
    indcom_df.loc[range_all_ic,'nHouse'] = 0
    indcom_df.loc[range_all_ic,'residents'] = 0
    indcom_df.loc[range_all_ic,'specialFac'] = 0

    ind_df = indcom_df[indcom_df['OccBld'] == 'Ind'].copy()
    com_df = indcom_df[indcom_df['OccBld'] == 'Com'].copy()
    ind_df.reset_index(drop=True,inplace=True)
    com_df.reset_index(drop=True,inplace=True)
            
        
    #%% Step 19,20 Generate school and hospitals along with their attributes

    # Assumption 14 and 15: For example : 1 school per 10000 individuals,
    # 1 hospital per 25000 individuals
    nsch = round(nindiv/nsch_pi) # Number of schools
    nhsp = round(nindiv/nhsp_pi) # Number of hospitals

    if nsch == 0:
        print("WARNING: Total population",nindiv,"is less than the user-specified "\
              "number of individuals per school",nsch_pi,". So, total school for "\
              "this population = 1 (by default) ")
        nsch = 1

    if nhsp == 0:
        print("WARNING: Total population",nindiv,"is less than the user-specified "\
              "number of individuals per hospital",nhsp_pi,". So, total hospital for "\
              "this population = 1 (by default) ")
        nhsp = 1

    nsh = np.array([nsch,nhsp])
    nsh_cs = np.cumsum(nsh)
    occbld_label_sh = ['Edu','Hea']
    specialFac = [1,2] # Special facility label
    schhsp_df = pd.DataFrame(np.nan, index = range(0, nsch+nhsp),
                            columns=['zoneID', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'lut_number','OccBld','lrstype','CodeLevel',
                                      'nstoreys'])
    t14= tables['t14'][0] # Extract Table 14
    a=0
    for i in range(0,len(t14)): # First school, then hospital
        attr_sh = t14[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        fpt_sh = np.fromstring(attr_sh[0], dtype=float, sep=',')
        nstorey_sh = np.fromstring(attr_sh[1], dtype=int, sep=',')
        codelevel_sh = np.fromstring(attr_sh[2], dtype=float, sep=',')
        lrs_sh = np.fromstring(attr_sh[3], dtype=float, sep=',')
        range_sh = range(a,nsh_cs[i])
        a = nsh_cs[i]
        # Generate footprints
        schhsp_df.loc[range_sh,'fptarea'] = np.random.uniform(\
                np.min(fpt_sh),np.max(fpt_sh), size=(nsh[i],1)).reshape(nsh[i],)
        # Generate number of storeys
        schhsp_df.loc[range_sh,'nstoreys'] =randint(np.min(nstorey_sh),\
                  np.max(nstorey_sh)+1,size=(nsh[i],1)).reshape(nsh[i],)
        # Generate code compliance
        cc_number_sh = multinomial(nsh[i],codelevel_sh,size=1)
        schhsp_df.loc[range_sh,'CodeLevel'] =\
                          dist2vector(code_level, cc_number_sh,nsh[i],'shuffle')
        # Generate LRS
        lrs_number_sh = multinomial(nsh[i],lrs_sh,size=1)
        schhsp_df.loc[range_sh,'lrstype'] =\
                          dist2vector(lrs_types,lrs_number_sh,nsh[i],'shuffle')
        schhsp_df.loc[range_sh,'OccBld']= occbld_label_sh[i] 

        # Assign special facility label  
        schhsp_df.loc[range_sh,'specialFac'] = specialFac[i]                 

    # Assign number of households, Residents, 
    range_all_sh = range(0,len(schhsp_df))
    schhsp_df.loc[range_all_sh,'nHouse'] = 0
    schhsp_df.loc[range_all_sh,'residents'] = 0


    #%% Assign zoneIds for Industrial and Commercial buildings

    # The number of industrial and commercial buildings are estimated using the
    # following 2 methods:
    # Method 1: Assumption of number of industrial or commercial building per
    #           1000 individuals. (Done in steps 17,18)
    # Method 2: Table 9 specifies what the occupancy type distribution should be 
    #           in different land use types. This gives a different estimate of the
    #           number of the buiildings as compared to Method 1. (Done here)
    # To make these two Methods compatible, the value from Method 1 is treated as 
    # the actual value of the buildings, and Method 2 is used to ensure that
    # these buildings are distributed in such a way that they follow Table 9.
    # 
    # The following method of assigning the ZoneIDs treats the mixed used zones
    # (residential, residential+commercial) and purely industrial or commercial
    # zones as 2 separate cases.
    #
    # For each of the following 2 cases, we need to first find the number of
    # industrial and commercial buildings in each zone

    # Case 1: For industrial/commercial buildings in residential areas_____________
    for i in landuse_res_df.index:
        #Occupancy type distribution for a zone
        otd = t9[lutidx[landuse_res_df.loc[i,'LuF']]]
        if otd[1]==0 and otd[2]==0: 
            # If neither industrial nor commercial buildings exist
            landuse_res_df.loc[i,'ind_weightage'] = 0
            landuse_res_df.loc[i,'com_weightage'] = 0
            continue
        # Number of residential + rescom building
        Nrc = landuse_res_df.loc[i, 'No_of_res_buildings']
        
        # Tb = total possible number of buildings in a zone (all accupancy types)
        #      This is used as weightage factor to distribute the buildings 
        #      according to Method 2. 
        if otd[0] == 0 and otd[3]==0:
            Tb = Nrc # If neither residential nor res+com exist
            print('If population exists, but neither residential nor '\
                  'residential+commercial buildings are allowed, there is '\
                  'inconsistency between population and current row in table 9.'\
                  'Therefore, it is assumed that total number of buildings in '\
                  'zoneID', landuse_res_df.loc[i,'zoneID'],\
                  '= no. of residential buildings in this zone.')
            print('Also, consider allowing residential and/or res+com building '\
                  'to this zone in Table 9, if it is assigned population.')
        else:  
            Tb = Nrc/(otd[0]+otd[3]) # If either residential or res+com exist  

        #Calculate the number of industrial buildings using Table 9   
        if otd[1]>0:
            landuse_res_df.loc[i,'ind_weightage'] = ceil(Tb * otd[1])
            #landuse_res_df.loc[i,'No_of_ind_buildings'] = ceil(Tb * otd[1])
        else:
          # landuse_res_df.loc[i,'No_of_ind_buildings'] = 0
          landuse_res_df.loc[i,'ind_weightage'] = 0
            
        #Calculate the number of commercial buildings using Table 9     
        if otd[2]>0:
            landuse_res_df.loc[i,'com_weightage'] = ceil(Tb * otd[2])
            #landuse_res_df.loc[i,'No_of_com_buildings'] = ceil(Tb * otd[2])
        else:
            landuse_res_df.loc[i,'com_weightage'] = 0
            #landuse_res_df.loc[i,'No_of_com_buildings'] = 0

            
    # If number of buildings (industrial/commercial) estimated from Method 2(in the
    # above steps of Case 1) exceeds the number of buildings estimated from 
    # Method 1, treat the value from Method 1 as the upper limit. 
    # Then, using the number of buildings from Method 2 as weightage factor,
    # distribute the number of  buildings from Method 1 proportionally to
    # all the mixed use zones. This situation arises if the number of 
    # industrial/commercial buildings per 1000 people is low.
    #
    # Otherwise, if the number of industrial/commercial buildings estimated from
    # Method 1 is larger than that estimated  from Method 2, it is assumed that the
    # number of buildings is large enough not to fit into the mixed use zones
    # being considered under Case 1, and the additional buildings not assigned into
    # mixed use zones is assigned under case 2 in the following section.
    # 
    # This method requires the area of industrial/commercial buildings in the 
    # mixed use zones to be checked separately to see if they fit into these zones.

    com_wt = landuse_res_df['com_weightage'].copy()   
    if com_wt.sum() > ncom:
        landuse_res_df['No_of_com_buildings'] = np.floor(ncom*com_wt/com_wt.sum())
    else:
        landuse_res_df['No_of_com_buildings'] = com_wt

    ind_wt = landuse_res_df['ind_weightage'].copy()   
    if ind_wt.sum() > nind:
        landuse_res_df['No_of_ind_buildings'] = np.floor(nind*ind_wt/ind_wt.sum())
    else:
        landuse_res_df['No_of_ind_buildings'] = ind_wt    

          
    landuse_res_df['No_of_ind_buildings'] =\
                        landuse_res_df['No_of_ind_buildings'].astype('int')
    landuse_res_df['No_of_com_buildings'] =\
                        landuse_res_df['No_of_com_buildings'].astype('int')
                        
    # Number and area of commercial buildings to be assigned    
    nCom_asgn = landuse_res_df['No_of_com_buildings'].sum()
    nCom_asgn_area = com_df.loc[range(0, nCom_asgn),'fptarea'].sum() 
    # Number and area of industrial buildings to be assigned
    nInd_asgn = landuse_res_df['No_of_ind_buildings'].sum()
    nInd_asgn_area = ind_df.loc[range(0,nInd_asgn),'fptarea'].sum()


    # Assign zoneID to industrial buildings (if any) in residential areas
    zoneID_r_i = dist2vector(list(landuse_res_df['zoneID']),\
                list(landuse_res_df['No_of_ind_buildings']),nInd_asgn,'shuffle')
    ind_df.loc[range(0,nInd_asgn),'zoneID'] = list(map(int,zoneID_r_i))

    # Assign zoneID to commercial buildings (if any) in residential areas
    zoneID_r_c = dist2vector(list(landuse_res_df['zoneID']),\
                list(landuse_res_df['No_of_com_buildings']),nCom_asgn,'shuffle')
    com_df.loc[range(0,nCom_asgn),'zoneID'] = list(map(int,zoneID_r_c))


    # Back-calculated number of commercial buildings per 1000 people        
    #nCom_asgn/(len(individual_df)/1000)

    # Case 2 For industrial/commercial buildings in non-residential areas__________

    # Number of industrial buildings that have not been assigned
    nInd_tba = int(len(ind_df) - nInd_asgn)
    # Number of commercial buildings that have not been assigned
    nCom_tba = int(len(com_df) - nCom_asgn)

    # Before assigning zones to buildings, find out the area available for buildings
    # in each zones. Since no population is assigned to residential and commercial
    # buildings, the number of buildings in a zone is controlled solely by area.
    for i in landuse_ic_df.index:
        #Occupancy type distribution for a zone
        otd = t9[lutidx[landuse_ic_df.loc[i,'LuF']]]
        if otd[1]>0:
            landuse_ic_df.loc[i,'AreaAvailableForInd']=\
                                            AC_ind/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'AreaAvailableForInd']=0
    
        if otd[2]>0:
            landuse_ic_df.loc[i,'AreaAvailableForCom']=\
                                            AC_com/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'AreaAvailableForCom']=0
            
    # Check how many of the generated com/ind buildings fit into the available area
    ind_fptarea_cs = list(np.cumsum(ind_df['fptarea']))
    com_fptarea_cs = list(np.cumsum(com_df['fptarea']))

    # Total areas available for commercial and industrial buildings in all zones
    At_c= landuse_ic_df['AreaAvailableForCom'].sum()
    At_i = landuse_ic_df['AreaAvailableForInd'].sum()
    licidx = landuse_ic_df.index

    unassigned_ind_area = ind_fptarea_cs[-1]-nInd_asgn_area # Total - assigned
    if unassigned_ind_area <= At_i:
        landuse_ic_df.loc[licidx,'No_of_ind_buildings'] =\
            landuse_ic_df['AreaAvailableForInd']/At_i*nInd_tba
        landuse_ic_df['No_of_ind_buildings']=\
            landuse_ic_df['No_of_ind_buildings'].astype('int')
    else:
        print('Required industrial buildings do not fit into available land area.')
        sys.exit(1)

    unassigned_com_area = com_fptarea_cs[-1]-nCom_asgn_area
    if unassigned_com_area <= At_c:
        landuse_ic_df.loc[licidx,'No_of_com_buildings'] =\
            landuse_ic_df['AreaAvailableForCom']/At_c*nCom_tba
        landuse_ic_df['No_of_com_buildings']=\
            landuse_ic_df['No_of_com_buildings'].astype('int')
    else:
        print('Required commercial buildings do not fit into available land area.')
        sys.exit(1)
        
    # Begin assigning buildings to zones 
    # Assign zoneID to industrial buildings (if any) in industrial areas
    zoneID_ic_i = dist2vector(list(landuse_ic_df['zoneID']),\
                list(landuse_ic_df['No_of_ind_buildings']),nInd_tba,'shuffle')
    ind_df.loc[range(nInd_asgn,nInd_asgn+nInd_tba),'zoneID']=list(map(int,zoneID_ic_i))

    # Assign zoneID to commercial buildings (if any) in commercial areas
    zoneID_ic_c = dist2vector(list(landuse_ic_df['zoneID']),\
                list(landuse_ic_df['No_of_com_buildings']),nCom_tba,'shuffle')
    com_df.loc[range(nCom_asgn,nCom_asgn+nCom_tba),'zoneID']=list(map(int,zoneID_ic_c))


    #%% Find populations in each zones and assign it back to landuse layer
    for i in landuse.index:
        zidmask = resbld_df['zoneID'] == landuse.loc[i,'zoneID']
        if sum(zidmask) == 0: # if no population has been added to the zone
            landuse.loc[i,'populationAdded'] = 0
            continue
        else: # if new population has been added to the zone
            zone_nInd = resbld_df['residents'][zidmask]
            landuse.loc[i,'populationAdded'] = int(zone_nInd.sum())
    # population=Existing population, populationAdded=Projected future population
    # populationFinal = existing + future projected population
    landuse['populationFinal'] = landuse['population']+landuse['populationAdded']
    landuse['populationFinal'] = landuse['populationFinal'].astype('int')



    #%% Assign zoneIds for schools and hospitals
    # Assign schools and hospitals to zones starting from the highest 
    # population until the number of schools and hospitals are reached
    landuse_sorted = landuse.sort_values(by=['populationFinal'],\
                                                    ascending=False).copy()
    landuse_sorted.reset_index(inplace=True, drop=True)
    #Remove zones without population
    no_popl_zones = landuse_sorted['populationFinal']==0
    landuse_sorted =landuse_sorted.drop(index=landuse_sorted.index[no_popl_zones])

    sch_df = schhsp_df[schhsp_df['OccBld']=='Edu'].copy() #Educational institutions
    hsp_df = schhsp_df[schhsp_df['OccBld']=='Hea'].copy() #Health institutions

    sch_df.reset_index(drop=True,inplace=True)
    hsp_df.reset_index(drop=True,inplace=True)

    # Assign zoneIDs for schools/educational institutions
    sch_range = range(0,len(sch_df))
    if len(sch_df) <= len(landuse_sorted):
        sch_df.loc[sch_range, 'zoneID'] = landuse_sorted.loc[sch_range,'zoneID']
    else:
        iterations_s = ceil(len(sch_df)/len(landuse_sorted))
        a1_s= list(repeat(landuse_sorted['zoneID'].tolist(),iterations_s))
        a_s = list(chain(*a1_s))
        sch_df.loc[sch_range, 'zoneID'] = a_s[0:len(sch_df)]
            
    # Assign zoneIDs for hospitals/health institutions
    hsp_range= range(0,len(hsp_df))
    if len(hsp_df) <= len(landuse_sorted):
        hsp_range = range(0,len(hsp_df))
        hsp_df.loc[hsp_range, 'zoneID'] = landuse_sorted.loc[hsp_range,'zoneID']
    else:
        iterations_h = ceil(len(hsp_df)/len(landuse_sorted))
        a1_h= list(repeat(landuse_sorted['zoneID'].tolist(),iterations_h))
        a_h = list(chain(*a1_h))
        hsp_df.loc[hsp_range, 'zoneID'] = a_h[0:len(hsp_df)]


    #%% Concatenate the residential, industrial/commercial and special facilities
    # dataframes to obtain the complete building dataframe
    building_df=pd.concat([resbld_df,ind_df,com_df,sch_df,\
                            hsp_df]).reset_index(drop=True)
    building_df['nstoreys'] = building_df['nstoreys'].astype(int)

    #Assign exposure string
    building_df['expStr'] = building_df['lrstype'].astype(str)+'+'+\
                            building_df['CodeLevel'].astype(str)+'+'+\
                            building_df['nstoreys'].astype(str)+'s'+'+'+\
                            building_df['OccBld'].astype(str)
    # Assign building ids
    # lenbdf = len(building_df)
    # building_df.loc[range(0,lenbdf),'bldID'] = list(range(1,lenbdf+1))
    building_df.loc[range(len(resbld_df),len(building_df)),'bldID'] =\
                        list(range(len(resbld_df)+1,len(building_df)+1))
    building_df['bldID'] = building_df['bldID'].astype('int')


    #%% Step 21 Employment status of the individuals
    # Assumption 9: Only 20-65 years old individuals can work
    # Extract Tables 12 and 13
    t12 = np.array(tables['t12'][0][0],dtype=float) #[Female, Male]

    t13_f = np.array(tables['t13'][0][0],dtype=float) #Female
    t13_m = np.array(tables['t13'][0][1],dtype=float) #Male
    t13 = [t13_f,t13_m]

    # Identify individuals who can work
    working_females_mask = (individual_df['gender']==1) & \
                (individual_df['age']>=5) & (individual_df['age']<=9)
    working_males_mask = (individual_df['gender']==2) & \
                (individual_df['age']>=5) & (individual_df['age']<=9)
    potential_female_workers = individual_df.index[working_females_mask]
    potential_male_workers = individual_df.index[working_males_mask]
        
    # But according to Table 12, not all individuals who can work are employed,
    # so the labour force is less than 100%
    labourforce_female = sample(list(potential_female_workers),\
                                    int(t12[0]*len(potential_female_workers)))
    labourforce_male = sample(list(potential_male_workers),\
                                    int(t12[1]*len(potential_male_workers))) 
    # labourForce = 1 indicates that an individual is a part of labour force, but 
    # not necessarily employed.
    individual_df.loc[labourforce_female,'labourForce'] =1
    individual_df.loc[labourforce_male,'labourForce'] =1  

    # According to Table 13, the employment probability for labourforce differs
    # based on educational attainment status   
    for epd_array in t13: #Employment probability distribution for female and male
        count = 0
        ind_employed_idx =[]
        for epd in epd_array: # EPD for various educational attainment status
            # Individuals in labour force that belong to current EPD
            eamask = (individual_df['eduAttStat'] == education_value[count]) & \
                    (individual_df['labourForce']==1)
            nInd_in_epd = sum(eamask)
            if nInd_in_epd == 0:
                continue
            
            nInd_employed = int(epd*nInd_in_epd)
            if nInd_employed == 0:
                continue
            ind_ea_labourforce = list(individual_df.index[eamask])
            ind_employed_idx = sample(ind_ea_labourforce, nInd_employed)
            individual_df.loc[ind_employed_idx,'employed'] = 1
            
            #Check ouput epd (for debugging)
            #print(epd,':',len(ind_employed_idx)/len(ind_ea_labourforce))
            
            count+=1
        
    #%% Step 22 Assign IndividualFacID
    # bld_ID of the building that the individual regularly visits 
    # (can be workplace, school, etc.)
    # Assumption 13: Each individual is working within the total study area extent.
    # Assumption 17: Each individual (within schooling age limits) goes to 
    #                school within the total study area extent.

    # indivFacID_1 denotes bldID of the schools
    # students (schoolEnrollment=1) go to, whereas, indivFacID_2 denotes bldID of
    # com, ind and rescom buildings where working people go to (workplace bldID).

    # Assign working places to employed people in indivFacID_2_________________
    # Working places are defined as occupancy types 'Ind','Com' and 'ResCom'
    workplacemask=(building_df['OccBld']=='Ind') | (building_df['OccBld']=='Com')\
                    | (building_df['OccBld'] == 'ResCom')
    workplaceidx = building_df.index[workplacemask]
    workplace_bldID = building_df['bldID'][workplaceidx].tolist()

    employedmask = individual_df['employed'] ==1
    employedidx = individual_df.index[employedmask]
    if len(employedidx)>len(workplaceidx):
        repetition = ceil(len(employedidx)/len(workplaceidx))
        workplace_sample_temp = list(repeat(workplace_bldID,repetition))
        workplace_sample = list(chain(*workplace_sample_temp))
    else:
        workplace_sample = workplace_bldID
    random.shuffle(workplace_sample)

    individual_df.loc[employedidx,'indivFacID_2'] = \
                                  workplace_sample[0:sum(employedmask)]

    # Assign school bldIDs to enrolled students in indivFacID_1________________
    schoolmask = building_df['OccBld']=='Edu'            
    schoolidx = building_df.index[schoolmask]
    school_bldID = building_df['bldID'][schoolidx].tolist()

    studentmask = individual_df['schoolEnrollment'] ==1
    studentidx = individual_df.index[studentmask]
    if len(studentidx)>len(schoolidx):
        repetition = ceil(len(studentidx)/len(schoolidx))
        school_sample_temp = list(repeat(school_bldID,repetition))
        school_sample = list(chain(*school_sample_temp))
    else:
        school_sample = school_bldID
    random.shuffle(school_sample)

    individual_df.loc[studentidx,'indivFacID_1'] = \
                                  school_sample[0:sum(studentmask)]  

    # Replace missing values with -1 instead of NaN
    individual_df['indivFacID_1'] = individual_df['indivFacID_1'].fillna(-1)
    individual_df['indivFacID_2'] = individual_df['indivFacID_2'].fillna(-1)  


    #%% Step 23 Assign community facility ID (CommFacID) to household layer
    # CommFacID denotes the bldID of the hospital the households usually go to.

    # In this case, randomly assign bldID of hospitals to the households, but in 
    # next version, households must be assigned hospitals closest to their location
    hospitalmask = building_df['OccBld']=='Hea'
    hospitalidx = building_df.index[hospitalmask]
    hospital_bldID = building_df['bldID'][hospitalidx].tolist()
    repetition = ceil(len(household_df)/len(hospitalidx))
    hospital_sample_temp = list(repeat(hospital_bldID,repetition))
    hospital_sample = list(chain(*hospital_sample_temp))
    random.shuffle(hospital_sample)

    household_df.loc[household_df.index,'CommFacID'] =\
                                    hospital_sample[0:len(household_df)]

    #%% Step 24 Assign repValue
    # Assumption 12: Unit price for replacement wrt occupation type and 
    # special facility status of the building

    # Assign unit price
    for occtype in Unit_price:
        occmask = building_df['OccBld'] == occtype
        occidx = building_df.index[occmask]
        building_df.loc[occidx, 'unit_price'] = Unit_price[occtype]
        
    building_df['repValue'] = building_df['fptarea'] *\
                            building_df['nstoreys']* building_df['unit_price']


    #%% Remove unnecessary columns and save the results 
    building_df = building_df.drop(columns=\
            ['lut_number','lrstype','CodeLevel','nstoreys','OccBld','unit_price'])
    household_df = household_df.drop(columns=\
            ['income_numb','zoneType','zoneID','approxFootprint'])
    individual_df = individual_df.drop(columns=\
                        ['schoolEnrollment','labourForce','employed'])
        
    # Rename indices to convert all header names to lowercase
    building_df.rename(columns={'zoneID':'zoneid','bldID':'bldid','expStr':'expstr',\
      'specialFac':'specialfac','repValue':'repvalue','nHouse':'nhouse'},\
                                                              inplace=True)
    household_df.rename(columns={'bldID':'bldid','hhID':'hhid','nIND':'nind',\
                                'CommFacID':'commfacid'}, inplace=True)
    individual_df.rename(columns={'hhID':'hhid','indivID':'individ',\
      'eduAttStat':'eduattstat','indivFacID_1':'indivfacid_1',\
      'indivFacID_2':'indivfacid_2'}, inplace=True)
    landuse_shp.rename(columns={'zoneID':'zoneid','LuF':'luf',\
      'densityCap':'densitycap','floorAreaR':'floorarear',\
      'avgIncome':'avgincome'}, inplace=True)                                                                                                     

    #%% Generate building centroid coordinates

    histo = building_df.groupby(['zoneid'])['zoneid'].count()
    max_val = building_df.groupby(['zoneid'])['fptarea'].max()
    landuse_layer = landuse_shp
    building_layer = building_df
    final_list = []

    for i in range(len(histo)):
        df = landuse_layer[landuse_layer['zoneid'] == histo.index[i]].copy()
        bui_indx = building_layer['zoneid'] == histo.index[i]
        bui_attr = building_layer.loc[bui_indx].copy()
        
        rot_a = random.randint(10, 40)
        rot_a_rad = rot_a*math.pi/180

        separation_val = math.sqrt(max_val.values[i])/abs(math.cos(rot_a_rad))
        separation_val = round(separation_val, 2)
        boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
        boundary_approach = round(boundary_approach, 2)
        
        df2 = df.buffer(-boundary_approach)
        df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
        df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
        
        xmin, ymin, xmax, ymax = df2.total_bounds    
        xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
        ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
        
        pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
        points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
        grid = gpd.GeoSeries(points, crs=df.crs)
        grid.name = 'geometry'
        
        gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
        
        def buff(row):
            return row.geometry.buffer(row.buff_val, cap_style = 3)
        
        if len(gridinside) >= histo.values[i]:
            gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
            gridinside['xcoord'] = gridinside.geometry.x
            gridinside['ycoord'] = gridinside.geometry.y
            
            buffer_val = np.sqrt(list(bui_attr.fptarea))/2
            buffered = gridinside.copy()
            buffered['buff_val'] = buffer_val[0:len(gridinside)]
            
            buffered['geometry'] = buffered.apply(buff, axis=1)
            polyinside = buffered.rotate(rot_a, origin='centroid')
            
            polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
            polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
            polyinside2['fid'] = list(range(1,len(polyinside2)+1))
            
            bui_attr['fid'] = list(range(1,len(bui_attr)+1))
            bui_joined = polyinside2.merge(bui_attr, on='fid')
            bui_joined = bui_joined.drop(columns=['fid'])
            
            bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
            bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
            
        elif len(gridinside) < histo.values[i]:
            separation_val = math.sqrt(max_val.values[i])
            separation_val = round(separation_val, 2)
            boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
            boundary_approach = round(boundary_approach, 2)
            
            df2 = df.buffer(-boundary_approach, 200)
            df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
            df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
            
            xmin, ymin, xmax, ymax = df2.total_bounds    
            xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
            ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
            
            pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
            points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
            grid = gpd.GeoSeries(points, crs=df.crs)
            grid.name = 'geometry'
            
            gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
            
            gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
            gridinside['xcoord'] = gridinside.geometry.x
            gridinside['ycoord'] = gridinside.geometry.y
            
            buffer_val = np.sqrt(list(bui_attr.fptarea))/2
            buffered = gridinside.copy()
            buffered['buff_val'] = buffer_val[0:len(gridinside)]
            
            buffered['geometry'] = buffered.apply(buff, axis=1)
            polyinside = buffered.rotate(0, origin='centroid')
            
            polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
            polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
            polyinside2['fid'] = list(range(1,len(polyinside2)+1))
            
            bui_attr['fid'] = list(range(1,len(bui_attr)+1))
            bui_joined = polyinside2.merge(bui_attr, on='fid')
            bui_joined = bui_joined.drop(columns=['fid'])
            
            bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
            bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))

        final_list.append(bui_joined)

    final = pd.concat(final_list)
    temp_cols = final.columns.tolist()
    new_cols = temp_cols[1:] + temp_cols[0:1]
    final = final[new_cols]

    temp_cols2 = landuse_shp.columns.tolist()
    new_cols2 = temp_cols2[1:] + temp_cols2[0:1]
    landuse_shp = landuse_shp[new_cols2]   

    return final, household_df, individual_df, landuse_shp
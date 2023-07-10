import numpy as np
import matplotlib.pyplot as plt
import calendar

import yaml

names = yaml.safe_load( open('names.yaml', 'r', encoding='utf-8') )

for nationality in names['nationalities'].keys():
    
    if 'inherit' in names['nationalities'][nationality].keys():
        for inherited_ethnicity in names['nationalities'][nationality]['inherit']:
            names['nationalities'][nationality][inherited_ethnicity.split(':')[1]] = names['nationalities'][
                inherited_ethnicity.split(':')[0]
            ][
                inherited_ethnicity.split(':')[1]
            ]
        del names['nationalities'][nationality]['inherit']
        
    for ethnicity in names['nationalities'][nationality].keys():
        if 'first_names' not in names['nationalities'][nationality][ethnicity]:
            names['nationalities'][nationality][ethnicity]['first_names'] = []
        if 'last_names' not in names['nationalities'][nationality][ethnicity]:
            names['nationalities'][nationality][ethnicity]['last_names'] = []
        if 'inherit_first_names' in names['nationalities'][nationality][ethnicity]:
            for inherited_first_names in names['nationalities'][nationality][ethnicity]['inherit_first_names']:
                names['nationalities'][nationality][ethnicity]['first_names'].extend(names['nationalities'][
                    inherited_first_names.split(':')[0]
                ][
                    inherited_first_names.split(':')[1]
                ]['first_names'])
            del names['nationalities'][nationality][ethnicity]['inherit_first_names']
        if 'inherit_last_names' in names['nationalities'][nationality][ethnicity]:
            for inherited_last_names in names['nationalities'][nationality][ethnicity]['inherit_last_names']:
                names['nationalities'][nationality][ethnicity]['last_names'].extend(names['nationalities'][
                    inherited_last_names.split(':')[0]
                ][
                    inherited_last_names.split(':')[1]
                ]['last_names'])
            del names['nationalities'][nationality][ethnicity]['inherit_last_names']

#cleanup: substitute "_" for " " in countries
for nationality in list(names['nationalities'].keys()):
    if '_' in nationality:
        names['nationalities'][nationality.replace('_',' ')] = names['nationalities'][nationality]
        del names['nationalities'][nationality]
            
k_value = 32

color = { 'black' : 232,
    'offwhite' : 255,
    'skyblue' : 39,
    'iceblue' : 51,
    'forest' : 28,
    'red' : 196,
    'yellow' : 226 }

phases_per_match = 24
default_goalkeepers_per_club = 2
high_quarterly_revenue = 500e6
base_matchday_revenue = 200000
matches_between_transfer_window = 10
starting_player_count_on_roster = 25
player_priority_factor = 50 # the discrepancy in team stat and player stat that causes the player's value for that club to double/halve

entity_id = 0
entity_lookup = []

def date_to_calendar_args(date_str, is_american = True):
    date_ind = date_str.split('/')
    if is_american:
        month = int(date_ind[0])
        day = int(date_ind[1])
    else:
        day = int(date_ind[0])
        month = int(date_ind[1])
    year = int(date_ind[2])
    return year, month, day
    
def calendar_args_to_date(year, month, day, is_american = True):
    return str(month)+'/'+str(day)+'/'+str(year)

def incr_date(start_date, days_to_incr, weekdays = [0,1,2,3,4,5,6]):
    incr_i = 0
    year, month, day = date_to_calendar_args(start_date)
    nc = calendar.TextCalendar(calendar.SUNDAY)
    for m in range(month,13):
      for i in nc.itermonthdays(year,m):
        if i != 0 and (month != m or i >= day):
          if calendar.weekday(year,m,i) in weekdays:
            if incr_i == days_to_incr:
              return calendar_args_to_date(year,m,i)
            incr_i += 1
    next_year = year + 1
    while next_year < year + 100: # set limit to a century
      for m in range(1,13):
        for i in nc.itermonthdays(next_year,m):
          if i != 0:
            if calendar.weekday(next_year,m,i) in weekdays:
              incr_i += 1
              if incr_i == days_to_incr:
                return calendar_args_to_date(next_year,m,i)
              incr_i += 1
      next_year += 1

def prob_win(a, b, algo_constant = 400):
    prob_a = 1 / (1 + 10**((b - a) / algo_constant))
    return prob_a

def update_ratings(a, b, which_won, k = k_value):
    a_1 = a + k * (which_won - prob_win(a, b))
    b_1 = b + k * ((1 - which_won) - prob_win(b, a))
    return a_1, b_1

def play_match(a, b, verbose=False):
    #Determine outcome of match
    
    # v1: random based on general stat
    #a_stat = a.club_stat()
    #b_stat = b.club_stat()
    #goals_for_a = np.random.randint( 0, int(1 / (1 + 10**((b_stat[2] - a_stat[0]) / 100)) * 10) + 1 )
    #goals_for_b = np.random.randint( 0, int(1 / (1 + 10**((a_stat[2] - b_stat[0]) / 100)) * 10) + 1 )
    
    # v2: using rudimentary formation
    
    #helper functions
    def attack_through_backline(attacking_frontline, defending_backline):
        attacking_power = 0
        for attacker in attacking_frontline:
            attacking_power += attacker.attack
        defensive_resilience = 0
        for defender in defending_backline:
            defensive_resilience += defender.defend
        shot_likelihood = 1 / (1 + 10**((defensive_resilience - attacking_power) / 400))
        if np.random.random() < shot_likelihood:
            #print('Shot fired!')
            return True
        return False
    
    def pick_shot_taker(attacking_team_sheet):
        weight_total = 0
        potential_scorers = []
        potential_scorers_weight = []
        for p in attacking_team_sheet.attack:
            weight = 4 * p.attack
            weight_total += weight
            potential_scorers.append(p)
            potential_scorers_weight.append(weight)
        for p in attacking_team_sheet.midfield:
            weight = 2 * p.attack
            weight_total += weight
            potential_scorers.append(p)
            potential_scorers_weight.append(weight)
        for p in attacking_team_sheet.backline:
            weight = p.attack
            weight_total += weight
            potential_scorers.append(p)
            potential_scorers_weight.append(weight)
        potential_scorers_weight = np.array(potential_scorers_weight) / weight_total # normalize
        return np.random.choice(potential_scorers, 1, p=potential_scorers_weight)[0]

    score = [[], []]

    n_phases = phases_per_match
    time_min = 0
    for i in range(n_phases):
        time_min = int(90 / n_phases * (i + 1 / 2))
        #who wins midfield battle?
        my_midfield = 0
        for midfielder in a.team_sheets[0].midfield:
            my_midfield += midfielder.midfield
        opp_midfield = 0
        for midfielder in b.team_sheets[0].midfield:
            opp_midfield += midfielder.midfield
        #print('midfield',my_midfield,opp_midfield,my_midfield / (my_midfield + opp_midfield))
        if np.random.random() < my_midfield / (my_midfield + opp_midfield):
            if verbose:
                print('  ' + str(a) + ' is attacking!')
            attacking_side = a
            defending_side = b
        else:
            if verbose:
                print('  ' + str(b) + ' is attacking!')
            attacking_side = b
            defending_side = a

        #do attackers skip defenders?
        shot = attack_through_backline(attacking_side.team_sheets[0].attack, defending_side.team_sheets[0].backline)
        
        #if so, does goalie block shot?
        if shot:
            shot_taker = pick_shot_taker(attacking_side.team_sheets[0])
            if verbose:
                print('    ' + shot_taker.full_name() + ' fires a shot!')
            goalkeeper = defending_side.team_sheets[0].goalkeeper
            goalkeeper_saves_shot = 1 / (1 + 10**((50 - goalkeeper.goalkeeping) / 50))
            if np.random.random() < goalkeeper_saves_shot:
                if verbose:
                    print('      ' + goalkeeper.full_name() + ' saves the shot!')
                continue
            if verbose:
                print('      ' + attacking_side.name + ' has scored! (' + str(time_min) + ' min)')
            if attacking_side == a:
                score[0].append(goal(shot_taker, time_min))
            else:
                score[1].append(goal(shot_taker, time_min))
    goals_for_a = score[0]
    goals_for_b = score[1]
    
    return goals_for_a, goals_for_b

def build_schedule(a):
    matchdays = []
    
    bye_slots = int(2**np.ceil(np.log2(len(a))) - len(a))
    
    a0, a1 = a[:int(len(a)/2)], a[int(len(a)/2):]
    if len(a0) <= len(a1):
        a0 = a0 + [None]*int(np.ceil(bye_slots/2))
        a1 = a1 + [None]*int(np.floor(bye_slots/2))
    else:
        a1 = a1 + [None]*int(np.ceil(bye_slots/2))

    for i in range(len(a0)):        
        this_matchday = []
        dial_roll = np.roll(a1,-1*i)
        for ii in range(len(a0)):
            this_matchday.append([a0[ii],dial_roll[ii]])
        matchdays.append(this_matchday)
    
    if len(a0) >= 2:
        in1 = build_schedule(a0)
        in2 = build_schedule(a1)
        for matchday in range(len(in1)):
            matchdays.append(in1[matchday]+in2[matchday])
        
    return matchdays

def make_team_sheet(team_club, formation = '4-4-2', verbose=False):
    backline = []
    midfield = []
    frontline = []
    bench = []
    goalkeeper = None
    
    lines = [int(line) for line in formation.split('-')]
    attack_size = lines[-1]
    midfield_size = np.sum(lines[1:-1])
    defend_size = lines[0]
    if attack_size + midfield_size + defend_size != 10:
        if verbose:
            print('Invalid formation: ' + str(formation))
        return False
    bench_size = 6
    
    stat_vals = []
    for i in range(100):
        stat_vals.append([])
    best_goalkeeper = None
    
    for club_player in team_club.players:
        if club_player.goalkeeping:
            if not best_goalkeeper:
                best_goalkeeper = club_player
            elif club_player.goalkeeping > best_goalkeeper.goalkeeping:
                best_goalkeeper = club_player
            continue
        stat_vals[club_player.attack].append([club_player,'attack'])
        stat_vals[club_player.midfield].append([club_player,'midfield'])
        stat_vals[club_player.defend].append([club_player,'defend'])
        stat_vals[club_player.overall()].append([club_player,'overall'])
    
    allotted_players = []
    for i, stat_val in enumerate(stat_vals[::-1]):
        #print('  Stat of ' + str(100-i-1))
        for player_stat in stat_val:
            if len(allotted_players) == 10:
                break
            #print('    '+str(player_stat[0].full_name())+','+str(player_stat[-1]))
            if player_stat[0] in allotted_players:
                continue
            if player_stat[-1] == 'attack':
                if len(frontline) < attack_size:
                    frontline.append(player_stat[0])
                    allotted_players.append(player_stat[0])
                    continue
            if player_stat[-1] == 'midfield':
                if len(midfield) < midfield_size:
                    midfield.append(player_stat[0])
                    allotted_players.append(player_stat[0])
                    continue
            if player_stat[-1] == 'defend':
                if len(backline) < defend_size:
                    backline.append(player_stat[0])
                    allotted_players.append(player_stat[0])
                    continue
                    
    
    for i, stat_val in enumerate(stat_vals[::-1]):
        #print('  Stat of ' + str(100-i-1))
        for player_stat in stat_val:
            if len(allotted_players) == 10 + bench_size:
                break
            if player_stat[0] in allotted_players:
                continue
            if player_stat[-1] == 'overall':
                bench.append(player_stat[0])
                allotted_players.append(player_stat[0])
                continue
        
    if verbose:
        print('goalkeeper: ' + str(best_goalkeeper.full_name() + ', ' + str(best_goalkeeper.goalkeeping)))
        print('frontline: ' + str([p0.full_name() + ', ' + str(p0.attack) for p0 in frontline]))
        print('midfield: ' + str([p0.full_name() + ', ' + str(p0.midfield) for p0 in midfield]))
        print('backline: ' + str([p0.full_name() + ', ' + str(p0.defend) for p0 in backline]))
        print('bench: ' + str([p0.full_name() + ', ' + str(p0.overall()) for p0 in bench]))
    
    new_team_sheet = team_sheet(best_goalkeeper, backline, midfield, frontline, bench)
    team_club.team_sheets.append(new_team_sheet)
    
    return True

def club_priorities(prioritizing_club): # currently unused, should be developed later
    priorities = []
    attack, midfield, defend = prioritizing_club.club_stat()
    weakest_stat = np.min([attack, midfield, defend])
    if weakest_stat == attack:
        priorities.append('attack')
    elif weakest_stat == midfield:
        priorities.append('midfield')
    elif weakest_stat == defend:
        priorities.append('defend')
    return priorities

def player_value_to_club(assessed_player, assessing_club, verbose=False):
    my_club_stats = np.array(assessing_club.club_stat([assessed_player]))

    if verbose:
        print('\n',assessed_player.player_info(),'\n',assessed_player.attack,assessed_player.midfield,assessed_player.defend,assessed_player.market_value())

    weights = 100 - my_club_stats
    
    assessed_val_num = weights[0] * 2**((assessed_player.attack - my_club_stats[0]) / 50) + \
                       weights[1] * 2**((assessed_player.midfield - my_club_stats[1]) / 50) + \
                       weights[2] * 2**((assessed_player.defend - my_club_stats[2]) / 50)
    assessed_val_denom = np.sum(weights)
    assessed_val = int(assessed_val_num / assessed_val_denom * assessed_player.market_value())
    if verbose:
        print('€' + format(assessed_val, ",d"))
    return assessed_val

def transfer_player(moving_player, from_club, to_club, fee = 0):
    for club_player in from_club.players:
        if club_player.id == moving_player.id:
            from_club.players.remove(club_player)
            to_club.players.append(club_player)
            club_player.club = to_club.name
            from_club.funds += fee
            to_club.funds -= fee
            
def attempt_player_transfer(moving_player, from_club, to_club, fee, verbose=False):
    if to_club.funds < fee:
        if verbose:
            print(to_club.name + ' lacks funds for purchase of ' + moving_player.full_name())
        return False
    
    if len(from_club.players) <= 18:
        if verbose:
            print(from_club.name + ' will not sell any more players due to squad size')
        return False
    
    # Decide whether the club receiving the offer would accept
    ratio_for_accept = 0.85
    from_club_value = player_value_to_club(moving_player, from_club)
    if fee < ratio_for_accept * from_club_value:
        if verbose:
            print(from_club.name + ' rejects sale of ' + moving_player.full_name())
        return False
    
    if verbose:
        print(moving_player.full_name() + ' sold to ' + to_club.name)
    transfer_player(moving_player, from_club, to_club, fee)
    
    for from_club_team_sheet in from_club.team_sheets:
        if moving_player == from_club_team_sheet.goalkeeper:
            from_club.team_sheets.remove(from_club_team_sheet)
            continue
        elif moving_player in (from_club_team_sheet.attack + from_club_team_sheet.backline + from_club_team_sheet.midfield + from_club_team_sheet.bench):
            from_club.team_sheets.remove(from_club_team_sheet)
            continue
            
    if len(from_club.team_sheets) == 0:
        make_team_sheet(from_club)
    
    return True

#small classes (not derived from entity) go here
class goal:
    def __init__(self, scorer, time): #add more later to be used for statistics
        self.scorer = scorer
        self.time = time

#now for entity classes
class entity:
    def __init__(self):
        global entity_id
        self.id = entity_id
        entity_id += 1
        entity_lookup.append(self)
        
    def entity_attributes(self):
        entity_attr_str = 'object ' + str(self.id) + '\n'
        for attr in vars(self):
            entity_attr_str += attr + ': '
            entity_attr_str += str(getattr(self, attr)) + '\n'
        return entity_attr_str

class player_profile:
    def __init__(self, nationality = '', club_name = '', player_value_low = 0, player_value_high = 0, weekly_wage = 0, modifiers = []):
        self.nationality = nationality
        self.club_name = club_name
        self.player_value_low = player_value_low
        self.player_value_high = player_value_high
        self.weekly_wage = weekly_wage
        self.modifiers = modifiers
        
    def search(self, leagues):
        found_players = []
        for search_league in leagues:
          for sl_club in search_league.clubs:
            for club_player in sl_club.players:
              if ((not self.nationality) or self.nationality == club_player.nationality) \
                 and ((not self.club_name) or self.club_name == club_player.club) \
                 and ((not self.player_value_low) or club_player.market_value() >= self.player_value_low) \
                 and ((not self.player_value_high) or club_player.market_value() <= self.player_value_high):
                     include_player = True
                     for modifier in self.modifiers:
                       if modifier not in club_player.modifiers:
                         include_player = False
                         break
                     if include_player:
                       found_players.append(club_player)
        return found_players

class player(entity):
    def __init__(self, name = '', nationality = '', club = '', modifiers = []):
        entity.__init__(self)
        self.modifiers = modifiers
        if name and nationality:
            self.first_name = name.split(' ')[0]
            self.last_name = name.split(' ')[1]
        elif nationality:
            ethnicity = np.random.choice(list(names['nationalities'][nationality].keys()))
            self.first_name = np.random.choice(names['nationalities'][nationality][ethnicity]['first_names'])
            self.last_name = np.random.choice(names['nationalities'][nationality][ethnicity]['last_names'])
        else:
            nationality = np.random.choice(list(names['nationalities'].keys()))
            ethnicity = np.random.choice(list(names['nationalities'][nationality].keys()))
            self.first_name = np.random.choice(names['nationalities'][nationality][ethnicity]['first_names'])
            self.last_name = np.random.choice(names['nationalities'][nationality][ethnicity]['last_names'])
        self.nationality = nationality
        self.club = club
        
        self.goalkeeping = 0
        if 'goalkeeper' in modifiers:
            goalkeeping_bonus = 0
            goalkeeping_demerit = 0
            if 'competent keeper' in modifiers:
                goalkeeping_bonus += 50
            if 'error-prone keeper' in modifiers:
                goalkeeping_demerit += 20
            self.goalkeeping = np.random.randint(0 + goalkeeping_bonus, 100 - goalkeeping_demerit)
        
        attack_bonus = 0
        attack_demerit = 0
        if 'strong attack' in modifiers:
            attack_bonus += 80
        if 'goalkeeper' in modifiers:
            attack_demerit += 80
        self.attack = np.random.randint(0 + attack_bonus, 100 - attack_demerit)
        
        self.midfield = np.random.randint(0, 100)
        
        defend_demerit = 0
        if 'weak defend' in modifiers or 'goalkeeper' in modifiers:
            defend_demerit += 80
        self.defend = np.random.randint(0, 100 - defend_demerit)
        
    def full_name(self):
        return self.first_name + ' ' + self.last_name
        
    def overall(self):
        return int((self.attack + self.midfield + self.defend) / 3)
    
    def market_value(self):
        val = 20000 * self.overall()
        return val
    
    def player_info(self, include_market = False):
        info = self.first_name + ' ' + self.last_name
        info += '\n  ' + self.nationality
        info += '\n  ' + str(self.overall())
        info += '\n  ' + self.club
        if include_market:
            info += '\n  €' + format(self.market_value(), ',d')
        return info

class team_sheet(entity):
    def __init__(self, goalkeeper, backline, midfield, attack, bench):
        self.backline = backline
        self.midfield = midfield
        self.attack = attack
        self.bench = bench
        self.goalkeeper = goalkeeper
    
    #def __init__(self, starting_eleven, bench): # starting_eleven: { 'position' : Player } dict (11 long), bench: Player list (pref 7 long)
    #    self.starting_eleven = starting_eleven
    #    self.bench = bench
    #    self.backline = []
    #    self.midfield = []
    #    self.attack = []
    #    for starting_position in starting_eleven:
    #        if starting_position in ['RB','LB','CB']:
    #            self.backline.append(starting_eleven[starting_position])
    #        if starting_position in ['LM','RM','CM','DM','AM','LW','RW']:
    #            self.midfield.append(starting_eleven[starting_position])
    #        if starting_position in ['ST','LS','RS','CF','LF','RF']:
    #            self.attack.append(starting_eleven[starting_position])
    
class club(entity):
    def __init__(self, name, load_from_dict = None, modifiers = [], colors = None, elo = 1000, funds = 1e5, verbose=False):
        entity.__init__(self)
        self.name = name
        self.elo = elo
        self.players = []
        self.team_sheets = []
        self.active_team_sheet = None
        self.funds = funds
        self.weekly_sales = ( high_quarterly_revenue / 20 ) / 10 # 10 weeks in a quarter
        self.matchday_revenue = base_matchday_revenue
        self.financial_history = {}
        
        if colors:
            self.colors = colors
        else:
            self.colors = np.random.choice(list(color.values()),2)
            while self.colors[0] == self.colors[1]:
                self.colors = np.random.choice(list(color.values()),2)
        
        if load_from_dict:
            if 'name' in load_from_dict:
                self.name = load_from_dict['name']
            if 'elo' in load_from_dict:
                self.elo = int(load_from_dict['elo'])
            if 'funds' in load_from_dict:
                self.funds = int(load_from_dict['funds'])
            if 'players' in load_from_dict:
                for dict_player_name in load_from_dict['players']:
                    dp = load_from_dict['players'][dict_player_name]
                    self.players.append(player(dict_player_name,
                                              nationality = dp['nationality'],
                                              club = self.name))
        
        for i in range(len(self.players),starting_player_count_on_roster - default_goalkeepers_per_club):
            self.players.append(player('',
                                nationality = '',
                                club = self.name,
                                modifiers = modifiers))
        for i in range(default_goalkeepers_per_club):
            self.players.append(player('',
                                nationality = '',
                                club = self.name,
                                modifiers = ['goalkeeper']))
            
        make_team_sheet(self, verbose=verbose)
        
    def manage_transfers(self, available_leagues):
        # highest priority: maintain goalkeepers
        n_goalkeepers = 0
        for p in self.players:
            if p.goalkeeping:
                n_goalkeepers += 1
        if n_goalkeepers < default_goalkeepers_per_club:
            gk = player_profile(modifiers = [ 'goalkeeper' ])
            player_targets = gk.search(available_leagues)
            
    def financial_benchmark(self, date_str):
        self.financial_history[date_str] = self.funds
    
    def __str__(self):
        return "\033[1m\33[48;5;" + str(self.colors[0]) + "m\33[38;5;" + str(self.colors[1]) + "m" + self.name + "\33[0m"*3
    
    def club_stat(self, exclude_players = None):
        attacks = []
        midfields = []
        defends = []
        for player in self.players:
            if exclude_players and player in exclude_players:
                continue
            attacks.append( player.attack )
            midfields.append( player.midfield )
            defends.append( player.defend )
        
        return np.mean(attacks), np.mean(midfields), np.mean(defends)
    
    def get_dict(self):
        club_dict = {}
        club_dict['name'] = self.name
        club_dict['elo'] = self.elo
        club_dict['funds'] = self.funds
        club_dict['players'] = {}
        for club_player in self.players:
            full_name = club_player.first_name + ' ' + club_player.last_name
            club_dict['players'][full_name] = {}
            club_dict['players'][full_name]['nationality'] = str(club_player.nationality)
            club_dict['players'][full_name]['stats'] = { 'attack' : club_player.attack,
                                            'midfield' : club_player.midfield,
                                            'defend' : club_player.defend }
        return club_dict
    
class tournament(entity):
    def __init__(self, qualification):
        self.qualification = qualification
    
class season(entity):
    def __init__(self, clubs, start_date, order = None):
        self.matchday = 0 # deprecated
        
        these_clubs = list(clubs)
        np.random.shuffle(list(clubs))
        # order not yet implemented
        #if not order:
        #    order = np.arange(len(clubs))
        #    np.random.shuffle(order)
        
        self.schedule = {}
        matchdays = build_schedule(these_clubs)
        n_matchdays = len(matchdays)
        this_matchday = 0
        this_date = start_date
        
        for i in range(n_matchdays):
            this_date = incr_date(this_date, 1, weekdays=[6]) # 6 = Sunday, restrict league matchdays to Sunday
            self.schedule[this_date] = matchdays[this_matchday]
            this_matchday += 1
    
class timeline(entity):
    def __init__(self, start_date):
        self.start_date = start_date
        self.current_date = start_date
        self.competitions = []
        
    def next_day(self, verbose = False):
        self.current_date = incr_date(self.current_date, 1)
        if verbose:
          print('\n'+self.current_date)
        for l in self.competitions:
          l.date(self.current_date, verbose = verbose)
    
class league(entity):
    def __init__(self, name, clubs = []):
        entity.__init__(self)
        self.name = name
        self.clubs = []
        for club in clubs:
            self.clubs.append( club )
        self.standings = [0]*len(clubs)
        self.goal_differentials = [0]*len(clubs)
        self.past_seasons = []
           
    def find_club(self, name):
        for club in self.clubs:
            if club.name == name:
                return club
            
    def get_index_from_club(self, club_obj):
        n = 0
        for club in self.clubs:
            if club == club_obj:
                return n
            n += 1
    
    def play_match(self, a, b, verbose = False):
        #a is home, b is away
        
        # legacy: support use of indices instead of club instances
        if isinstance(a, int):
            ind_a = a
            a = self.clubs[ind_a]
        else:
            a_rating = a.elo
            ind_a = self.get_index_from_club(a)
        if isinstance(b, int):
            ind_b = b
            b = self.clubs[ind_b]
        else:
            b_rating = b.elo
            ind_b = self.get_index_from_club(b)
        
        #Determine outcome of match
        #a_stat = a.club_stat()
        #b_stat = b.club_stat()
        #goals_for_a = np.random.randint( 0, int(1 / (1 + 10**((b_stat[2] - a_stat[0]) / 100)) * 10) + 1 )
        #goals_for_b = np.random.randint( 0, int(1 / (1 + 10**((a_stat[2] - b_stat[0]) / 100)) * 10) + 1 )
        goal_list = play_match(a, b)
        goals_for_a = len(goal_list[0])
        goals_for_b = len(goal_list[1])
        if goals_for_a > goals_for_b:
            outcome = 1
        elif goals_for_a == goals_for_b:
            outcome = 0.5
        else:
            outcome = 0
        
        # commented out: pure random:
        # outcome = np.random.randint(0, 3) / 2
        
        #Home side matchday sales
        a.funds += int(a.matchday_revenue * 2 / 3 + b.matchday_revenue * 1 / 3)
        
        #Update Elo ratings and standings accordingly
        a_rating, b_rating = update_ratings(a_rating, b_rating, outcome)
        if outcome == 0:
            self.standings[ind_b] += 3
        elif outcome == 0.5:
            self.standings[ind_a] += 1
            self.standings[ind_b] += 1
        elif outcome == 1:
            self.standings[ind_a] += 3
        self.goal_differentials[ind_a] += goals_for_a - goals_for_b
        self.goal_differentials[ind_b] += goals_for_b - goals_for_a
        
        if verbose:
            print( self.name + ' news: ' + a.name + (
                ' beat ' if outcome == 1 else (
                    ' lost to ' if outcome == 0 else ' drew against ') ) + b.name +
                 ' ' + str(goals_for_a) + '-' + str(goals_for_b) )
        
        a.elo = a_rating
        b.elo = b_rating
        a.matchday_revenue = int(base_matchday_revenue * a.elo / 1000)
        b.matchday_revenue = int(base_matchday_revenue * b.elo / 1000)
        
    def setup_season(self, year, verbose = True):
        self.current_season = season(self.clubs, r'8/1/'+str(year))
        
    def end_season(self, verbose = False):
        print(self.name + ': end of season')
        self.past_seasons.append(self.current_season)
        
    def date(self, this_date, verbose = False):
        if calendar.weekday(*date_to_calendar_args(this_date)) == 4: # 4 = Friday
            for lc in self.clubs:
                lc.financial_benchmark(this_date)
    
        if this_date in self.current_season.schedule:
            self.matchday(self.current_season.schedule[this_date], verbose = verbose)
            if this_date == list(self.current_season.schedule)[-1]:
              self.end_season()
        elif verbose:
            print(self.name + ': no matches today')
        
    def setup_matchday(self, order = None, verbose = False):
        if not order:
            order = np.arange(len(self.standings))
            np.random.shuffle(order)
            
        for i in range( int(len(order) / 2) ):
            i_0 = self.clubs[order[i * 2]]
            i_1 = self.clubs[order[i * 2 + 1]]
            self.play_match(i_0, i_1, verbose = verbose)
        
    def matchday(self, matches = None, order = None, verbose = False): # replace order with matches
        if matches:
          if verbose:
            print('\n=====Start of ' + self.name + ' matchday!=====')
          for match in matches:
            if not match[0] or not match[1]:
              continue
            self.play_match(*match, verbose = verbose)
          if verbose:
            print('  Standings at end of matchday:')
            self.show_standings()
        else:
          if not order:
            order = np.arange(len(self.standings))
            np.random.shuffle(order)
        
          if verbose:
            print('\n=====Start of ' + self.name + ' matchday!=====')
          for i in range( int(len(order) / 2) ):
            i_0 = self.clubs[order[i * 2]]
            i_1 = self.clubs[order[i * 2 + 1]]
            self.play_match(i_0, i_1, verbose = verbose)
            
          if verbose:
            print('  Standings at end of matchday:')
            self.show_standings()
                
    def show_standings(self):
        sort_by_standing = lambda standing_pair: standing_pair[0] + 0.00001 * standing_pair[2]
        standing_pairs = []
        for i in range(len(self.standings)):
            standing_pairs.append([self.standings[i],self.clubs[i],self.goal_differentials[i]])
        standing_pairs = sorted(standing_pairs, key=sort_by_standing)
        for i in standing_pairs[::-1]:
            print('    ' + i[1].name + ': ' + str(i[0]) + ' points, GD = ' + str(i[2]))

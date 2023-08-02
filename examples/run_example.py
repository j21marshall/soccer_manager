#!/usr/bin/env python3

import soccer_core as sc

france_names = [ 'Paris',
           'Marseille',
           'Toulouse',
           'Grenoble',
           'Calais',
           'La Rochelle',
           'Nice',
           'Clermont-Ferrand' ]
          
spain_names = [ 'Valencia',
           'Granada',
           'Madrid',
           'Barcelona',
           'Santiago',
           'Zaragoza',
           'Palma',
           'Valladolid' ]
          
league_clubs = []
for club_name in france_names:
    league_clubs.append(sc.club(club_name, country='France'))
    
fl = sc.league('Ligue du France',league_clubs)

mrsl = fl.find_club('Marseille')
clfd = fl.find_club('Clermont-Ferrand')

#for i in range(15): l.matchday(verbose=True)

spain_league_clubs = []
for club_name in spain_names:
    spain_league_clubs.append(sc.club(club_name, country='Spain'))
    
sl = sc.league('Liga del Rey',spain_league_clubs)

vdld = sl.find_club('Valladolid')
grnd = sl.find_club('Granada')

free_agents = []
for i in range(20): free_agents.append(sc.player())

#fl.setup_season(1970)
#sl.setup_season(1970)

n = sc.timeline('7/1/1970')
n.competitions.append(fl)
n.competitions.append(sl)

for i in range(5000):
   n.next_day(verbose=True)

#import matplotlib.pyplot as plt
#for spain_club in sl.clubs + fl.clubs:
#    plt.plot([spain_club.financial_history[k] for k in spain_club.financial_history])
#plt.show()

in_str = ""
while in_str != "break":
  try:
    exec(in_str)
  except Exception as e:
    print(e)
  in_str = input()

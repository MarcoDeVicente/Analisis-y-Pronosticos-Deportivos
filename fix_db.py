import sqlite3
import unidecode

def normalize_name(name):
    if not name: return ""
    return unidecode.unidecode(str(name)).lower().strip()

ucl_aliases = {
    'psg', 'paris saint-germain', 'paris sg', 'paris',
    'real madrid', 'arsenal', 'man city', 'manchester city',
    'barcelona', 'fc bayern', 'bayern munich', 'bayern munchen',
    'liverpool', 'inter de milan', 'inter', 'inter milan',
    'atletico madrid', 'ath madrid', 'atletico',
    'man united', 'manchester united', 'man. utd',
    'borussia dortmund', 'dortmund',
    'roma', 'as roma',
    'aston villa', 'porto', 'fc porto', 'oporto',
    'sporting', 'sporting cp', 'sporting clube de portugal',
    'psv', 'psv eindhoven', 'real betis', 'betis',
    'club brugge', 'club brugge kv', 'club brujas',
    'rb leipzig', 'leipzig', 'napoli', 'napoles',
    'galatasaray', 'galatasaray sk', 'villarreal', 'villarreal cf',
    'fenerbahce', 'fenerbahce sk', 'lille', 'lille osc',
    'feyenoord', 'feyenoord rotterdam',
    'shakhtar d.', 'shakhtar donetsk', 'fk shakhtar donetsk', 'shakhtar',
    'bodo/glimt', 'fk bodo/glimt', 'bodo glimt',
    'como', 'como 1907', 'stuttgart', 'vfb stuttgart',
    'lens', 'rc lens', 'racing club de lens',
    'slavia prague', 'sk slavia praha', 'slavia',
    'aek athens', 'aek', 'viking fk', 'viking',
    'lask', 'lask linz',
    'slovan bratislava', 'sk slovan bratislava',
    'sabah fk', 'sabah'
}

canonical_map = {
    'paris sg': 'PSG', 'paris saint-germain': 'PSG', 'paris': 'PSG', 'psg': 'PSG',
    'man city': 'Manchester City', 'manchester city': 'Manchester City',
    'man united': 'Manchester United', 'manchester utd': 'Manchester United', 'manchester united': 'Manchester United',
    'fc bayern': 'Bayern Munich', 'bayern munich': 'Bayern Munich', 'bayern munchen': 'Bayern Munich',
    'inter de milan': 'Inter Milan', 'inter': 'Inter Milan', 'inter milan': 'Inter Milan',
    'real madrid': 'Real Madrid',
    'atletico madrid': 'Atletico Madrid', 'ath madrid': 'Atletico Madrid', 'atletico': 'Atletico Madrid',
    'barcelona': 'Barcelona',
    'arsenal': 'Arsenal',
    'club brugge': 'Club Brugge', 'club brugge kv': 'Club Brugge', 'club brujas': 'Club Brugge',
    'sporting': 'Sporting CP', 'sporting cp': 'Sporting CP', 'sporting clube de portugal': 'Sporting CP',
    'psv': 'PSV', 'psv eindhoven': 'PSV',
    'roma': 'Roma', 'as roma': 'Roma',
    'aston villa': 'Aston Villa',
    'porto': 'Porto', 'fc porto': 'Porto', 'oporto': 'Porto',
    'real betis': 'Real Betis', 'betis': 'Real Betis',
    'rb leipzig': 'RB Leipzig', 'leipzig': 'RB Leipzig',
    'napoli': 'Napoli', 'napoles': 'Napoli',
    'galatasaray': 'Galatasaray', 'galatasaray sk': 'Galatasaray',
    'villarreal': 'Villarreal', 'villarreal cf': 'Villarreal',
    'fenerbahce': 'Fenerbahce', 'fenerbahce sk': 'Fenerbahce',
    'lille': 'Lille', 'lille osc': 'Lille',
    'feyenoord': 'Feyenoord', 'feyenoord rotterdam': 'Feyenoord',
    'shakhtar d.': 'Shakhtar Donetsk', 'shakhtar donetsk': 'Shakhtar Donetsk', 'fk shakhtar donetsk': 'Shakhtar Donetsk', 'shakhtar': 'Shakhtar Donetsk',
    'bodo/glimt': 'Bodo/Glimt', 'fk bodo/glimt': 'Bodo/Glimt', 'bodo glimt': 'Bodo/Glimt',
    'como': 'Como', 'como 1907': 'Como',
    'stuttgart': 'Stuttgart', 'vfb stuttgart': 'Stuttgart',
    'lens': 'Lens', 'rc lens': 'Lens', 'racing club de lens': 'Lens',
    'slavia prague': 'Slavia Prague', 'sk slavia praha': 'Slavia Prague', 'slavia': 'Slavia Prague',
    'aek athens': 'AEK Athens', 'aek': 'AEK Athens',
    'viking fk': 'Viking', 'viking': 'Viking',
    'lask': 'LASK', 'lask linz': 'LASK',
    'slovan bratislava': 'Slovan Bratislava', 'sk slovan bratislava': 'Slovan Bratislava',
    'sabah fk': 'Sabah FK', 'sabah': 'Sabah FK',
    'dortmund': 'Dortmund', 'borussia dortmund': 'Dortmund',
    'liverpool': 'Liverpool'
}

def get_canonical(name):
    norm = normalize_name(name)
    return canonical_map.get(norm, name)

def run():
    conn = sqlite3.connect('DB-Fut-Beis.db')
    c = conn.cursor()
    
    # 1. Clean up "Champions League" teams that are not in ucl_aliases
    c.execute("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga = 'Champions League'")
    for eid, nombre in c.fetchall():
        norm = normalize_name(nombre)
        if norm not in ucl_aliases:
            # Reassign their league to something else, or if they have no matches, delete?
            # They came from Champ.csv which means they belong to their domestic leagues... but which one?
            # It's better to just assign them to 'Otra Liga' or something, so they don't appear in UCL.
            c.execute("UPDATE futbol_equipos SET Liga = 'Otra Liga' WHERE Equipo_ID = ?", (eid,))
            print(f"Removed {nombre} from Champions League")

    # 2. Merge duplicate teams based on canonical_map
    c.execute("SELECT Equipo_ID, Nombre, Liga FROM futbol_equipos")
    teams = c.fetchall()
    
    # Group by canonical name
    canonical_groups = {}
    for eid, nombre, liga in teams:
        canon = get_canonical(nombre)
        if canon not in canonical_groups:
            canonical_groups[canon] = []
        canonical_groups[canon].append((eid, nombre, liga))
        
    for canon, group in canonical_groups.items():
        if len(group) > 1:
            print(f"Merging {canon}: {group}")
            # Pick a primary ID (preferably the one that is NOT 'Champions League' if there's a Big 5 league, or just the first)
            # Sort by Liga: Big 5 leagues preferred over Champions League
            def sort_key(x):
                liga = x[2]
                if liga in ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1']:
                    return 0
                if liga == 'Champions League':
                    return 1
                return 2
            
            group.sort(key=sort_key)
            primary_id = group[0][0]
            
            for eid, nombre, liga in group[1:]:
                # Update partidos
                c.execute("UPDATE futbol_partidos SET Local_ID = ? WHERE Local_ID = ?", (primary_id, eid))
                c.execute("UPDATE futbol_partidos SET Visitante_ID = ? WHERE Visitante_ID = ?", (primary_id, eid))
                c.execute("UPDATE OR IGNORE futbol_estadisticas SET Equipo_ID = ? WHERE Equipo_ID = ?", (primary_id, eid))
                # Delete duplicate team
                c.execute("DELETE FROM futbol_equipos WHERE Equipo_ID = ?", (eid,))
                
            # Update the name to the canonical name
            c.execute("UPDATE futbol_equipos SET Nombre = ? WHERE Equipo_ID = ?", (canon, primary_id))
            
    conn.commit()
    conn.close()
    print("Database fixed.")

if __name__ == '__main__':
    run()

import os
import glob
import graphviz
import sys

short = False
horizontal = False

def parse_shared_cpu_list(cpu_list_string):
    cpu_ids = []
    entries = cpu_list_string.split(',')
    
    for entry in entries:
        if '-' in entry:
            # Handle range (e.g., "0-3")
            start, end = map(int, entry.split('-'))
            cpu_ids.extend(range(start, end + 1))
        else:
            # Handle individual CPU (e.g., "5")
            cpu_ids.append(int(entry))
    
    return cpu_ids


def read_cache_info(cpu_id, cache_index_path):
    cache_info = {}
    try:
        with open(os.path.join(cache_index_path, 'level')) as f:
            cache_info['level'] = f.read().strip()

        with open(os.path.join(cache_index_path, 'size')) as f:
            cache_info['size'] = f.read().strip()

        with open(os.path.join(cache_index_path, 'type')) as f:
            cache_info['type'] = f.read().strip().lower()

        with open(os.path.join(cache_index_path, 'ways_of_associativity')) as f:
            cache_info['ways'] = f.read().strip()

        with open(os.path.join(cache_index_path, 'number_of_sets')) as f:
            cache_info['sets'] = f.read().strip()

        with open(os.path.join(cache_index_path, 'coherency_line_size')) as f:
            cache_info['line_size'] = f.read().strip()

        with open(os.path.join(cache_index_path, 'shared_cpu_list')) as f:
            cache_info['shared_cpus'] = f.read().strip()

        # Check for inclusivity
        # TODO: use cpuid for that info
        try:
            with open(os.path.join(cache_index_path, 'inclusive')) as f:
                cache_info['inclusive'] = f.read().strip()
        except FileNotFoundError:
            cache_info['inclusive'] = 'Unknown' 

        cache_info['cpu_id'] = cpu_id

    except FileNotFoundError:
        pass

    return cache_info

def create_graph(all_cache_info):
    dot = graphviz.Digraph(comment='CPU Cache Hierarchy')

    if horizontal:
        dot.attr(rankdir='LR')
    else:
        dot.attr(rankdir='TB')

    cache_nodes = {}

    # Create CPU nodes (round shape)
    for cpu_id in {cache_info['cpu_id'] for cache_info in all_cache_info}:
        dot.node(f"CPU{cpu_id}", label=f"CPU {cpu_id}", shape='circle')

    # Create cache nodes
    edges = []
    for cache_info in all_cache_info:
        shared_cpu_list = cache_info['shared_cpus'] if cache_info['shared_cpus'] else f"CPU{cache_info['cpu_id']}"
        cache_key = (
            cache_info['level'],
            cache_info['type'],
            shared_cpu_list
        )
        cache_id = f"L{cache_info['level']}_{cache_info['type']}_{shared_cpu_list.replace(',', '_')}"

        if cache_key not in cache_nodes:
            inclusivity = f"Inclusive: {cache_info['inclusive']}"
            if short:
                label = (f"L{cache_info['level']}{cache_info['type'].capitalize()[0].replace('U', '')} {cache_info['size']}\\n{cache_info['ways']}-way {cache_info['sets']} sets")
            else:
                label = (f"L{cache_info['level']} {cache_info['type'].capitalize()} Cache\n"
                        f"Size: {cache_info['size']}\n"
                        f"Ways: {cache_info['ways']}\n"
                        f"Sets: {cache_info['sets']}\n"
                        f"Line Size: {cache_info['line_size']} bytes\n"
                        f"{inclusivity}\n"
                        f"Shared CPUs: {shared_cpu_list}")
            dot.node(cache_id, label=label, shape='rect')
            cache_nodes[cache_key] = cache_id

        # Link L1 caches directly to the CPU
        if cache_info['level'] == '1':
            dot.edge(f"CPU{cache_info['cpu_id']}", cache_nodes[cache_key])
        else:
            # For higher-level caches (L2, L3), link them to the previous level cache
            previous_level = str(int(cache_info['level']) - 1)
            shared_cpu_ids = set(parse_shared_cpu_list(shared_cpu_list))
            found = False
            if cache_info["type"] == "data": acceptable_types = ["data"]
            elif cache_info["type"] == "instruction": acceptable_types = ["instruction"]
            else: acceptable_types = ['data', 'instruction', 'unified']

            for previous_type in acceptable_types:
                for previous_cache_info in all_cache_info:
                    if previous_cache_info['level'] == previous_level and previous_cache_info['type'] == previous_type:
                        previous_shared_cpu_ids = set(parse_shared_cpu_list(previous_cache_info['shared_cpus']))
                        if previous_shared_cpu_ids.issubset(shared_cpu_ids):
                            previous_cache_key = (
                                previous_level,
                                previous_type,
                                previous_cache_info['shared_cpus']
                            )
                            if previous_cache_key in cache_nodes:
                                e = (cache_nodes[previous_cache_key], cache_nodes[cache_key])
                                if e not in edges:
                                    dot.edge(*e)
                                    edges.append(e)
                                found = True
                                #break

            if not found:
                # If no specific lower-level cache found, link directly to the CPU
                dot.edge(f"CPU{cache_info['cpu_id']}", cache_nodes[cache_key])

    return dot

def main():
    global short, horizontal
    cpu_dirs = sorted(glob.glob('/sys/devices/system/cpu/cpu[0-9]*'))
    all_cache_info = []
    
    for v in sys.argv:
        if v == "--short": 
            short = True
            horizontal = True
        if v == "--lr":
            horizontal = True
        if v == "--tb":
            horizontal = False

    for cpu_dir in cpu_dirs:
        cpu_id = os.path.basename(cpu_dir).replace('cpu', '')
        cache_index_paths = sorted(glob.glob(os.path.join(cpu_dir, 'cache/index*')))

        for cache_index_path in cache_index_paths:
            cache_info = read_cache_info(cpu_id, cache_index_path)
            if cache_info:
                all_cache_info.append(cache_info)

    if all_cache_info:
        dot = create_graph(all_cache_info)
        dot_source = dot.source
        #print("Generated DOT content:")
        #print(dot_source)
        dot.render('cpu_cache_hierarchy_all_cpus', format='png', cleanup=False)
        print("Graphviz illustration generated and saved as 'cpu_cache_hierarchy_all_cpus.png'")
    else:
        print("No cache information found.")

if __name__ == "__main__":
    main()
 

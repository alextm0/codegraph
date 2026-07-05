import platform
import subprocess
import time
import json
import psutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))

def get_hardware_specs():
    specs = {
        "OS": platform.platform(),
        "Processor": platform.processor() or platform.machine(),
        "Python": platform.python_version(),
        "RAM_GB": round(psutil.virtual_memory().total / (1024**3), 1)
    }
    # Attempt to get precise CPU model on Mac
    if platform.system() == "Darwin":
        try:
            brand = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
            specs["Processor"] = brand
        except Exception:
            pass
    return specs

def get_neo4j_version():
    try:
        from codegraph.core.graph.connection import create_driver, load_config
        config = load_config("config.yaml")
        driver = create_driver(config)
        with driver.session() as session:
            result = session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS version")
            record = result.single()
            if record:
                return record["version"]
    except Exception as e:
        return f"Unknown (Error: {e})"
    return "Unknown"

def measure_indexing(repo_path: str, driver) -> tuple[float, int, int]:
    print(f"Measuring indexing cost for {repo_path}...")
    from codegraph.core.parser import parse_directory
    from codegraph.core.graph.graph_builder import clear_database, build_graph
    
    start = time.time()
    try:
        entities = parse_directory(repo_path, exclude_patterns=["tests", ".git"])
        clear_database(driver)
        counts = build_graph(driver, entities)
        duration = time.time() - start
        
        # Calculate totals
        node_keys = ("File", "Function", "Class", "Method")
        edge_keys = ("CONTAINS", "CALLS", "IMPORTS", "INHERITS_FROM")
        nodes = sum(counts.get(k, 0) for k in node_keys)
        edges = sum(counts.get(k, 0) for k in edge_keys)
        
        return duration, nodes, edges
    except Exception as e:
        print(f"Error indexing {repo_path}: {e}")
        return -1.0, 0, 0

def main():
    print("Gathering Hardware and Environment Specifications...")
    specs = get_hardware_specs()
    specs["Neo4j"] = get_neo4j_version()
    
    print("\n--- Experimental Configuration ---")
    for k, v in specs.items():
        print(f"{k}: {v}")
    
    print("\nParagraph for Paper:")
    print(f"All experiments were executed on a machine running {specs['OS']}, "
          f"equipped with a {specs['Processor']} and {specs['RAM_GB']} GB of RAM. "
          f"The system ran Python {specs['Python']} and Neo4j {specs['Neo4j']}.")

    # For indexing time, we can test on a known repo if it exists locally
    # We will assume repos are stored in .codegraph_cache/repos/ or projects/
    repos_to_test = [
        ("matplotlib", ".codegraph_cache/repos/matplotlib__matplotlib"),
        ("scikit-learn", ".codegraph_cache/repos/scikit-learn__scikit-learn"),
        ("django/django", ".codegraph_cache/repos/django__django"),
        ("sympy/sympy", ".codegraph_cache/repos/sympy__sympy")
    ]
    
    from codegraph.core.graph.connection import create_driver, load_config
    config = load_config("config.yaml")
    driver = create_driver(config)
    
    print("\n--- Indexing Cost ---")
    print(f"{'Repository':<15} | {'Nodes':<7} | {'Edges':<8} | {'Duration (s)':<12}")
    print("-" * 52)
    for name, path in repos_to_test:
        if Path(path).exists():
            duration, nodes, edges = measure_indexing(path, driver)
            print(f"{name:<15} | {nodes:<7,} | {edges:<8,} | {duration:.1f}s")
        else:
            print(f"{name:<15} | {'N/A':<7} | {'N/A':<8} | Not found at {path}")
            
    print("\nNote: Median query latency can be extracted from the sweep_summary.json or per_instance.jsonl after running the full ablation sweep.")

if __name__ == "__main__":
    main()

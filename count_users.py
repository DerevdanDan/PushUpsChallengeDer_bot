import json

def count_users_simple():
    """The easiest way to count users"""
    try:
        # Read your existing data file
        with open('fitness_challenge_data.json', 'r') as f:
            data = json.load(f)
        
        # Count users
        total_users = len(data)
        print(f"🤖 Total Users: {total_users}")
        
        # Show user IDs
        print("\n👥 User IDs:")
        for user_id in data.keys():
            print(f"  • {user_id}")
        
        # Count users with challenges
        users_with_challenges = 0
        active_challenges = 0
        
        for user_id, user_data in data.items():
            challenges = user_data.get('challenges', {})
            if challenges:
                users_with_challenges += 1
                
                # Count active challenges for this user
                for challenge in challenges.values():
                    if challenge.get('status') == 'active':
                        active_challenges += 1
        
        print(f"\n📊 Quick Stats:")
        print(f"  • Total Users: {total_users}")
        print(f"  • Users with Challenges: {users_with_challenges}")
        print(f"  • Active Challenges: {active_challenges}")
        
    except FileNotFoundError:
        print("❌ File 'fitness_challenge_data.json' not found!")
        print("Make sure you're in the same folder as your bot files.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    count_users_simple()
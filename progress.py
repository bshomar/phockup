import sys

class ProgressBar:
    def __init__(self, total_count, status_names):
        self.total_count = total_count
        self.processed_count = 0
        self.status_names = status_names
        self.count = dict(zip(status_names,[0]*len(status_names)))
        header = "\n%-10s%-10s" % ("Complete","Total")
        line = "\n%-10s%-10s" % (('-'*len('Complete')),('-'*len('Total')))
        values = "\n%%%-10.0f%-10d" % (0.0,self.total_count)
        for n in self.status_names:
            header += "%-10s" % n
            line += "%-10s" % ('-'* len(n))
            values += "%-10d" % self.count[n]
        sys.stderr.write(header )
        sys.stderr.write(line )
        sys.stderr.write(values )
        sys.stderr.flush()

    def increment(self,name):
        self.count[name] += 1
        self.processed_count += 1
        values = "\r%%%-10.0f" % (100*self.processed_count/self.total_count)
        values += "%-10d" % self.total_count
        for n in self.status_names:
            values += "%-10d" % self.count[n]
        sys.stderr.write(values)
        sys.stderr.flush()

    def done(self):
        sys.stderr.write("\n")
        sys.stderr.flush()

if __name__ == '__main__':
    import time
    max = 50
    names = ['Copy', 'Move', 'Duplicate', 'Other']
    bar = ProgressBar(max, names)
    for i in range(0,max):
        bar.increment(names[int(i%4)])
        time.sleep(0.1)
    bar.done()